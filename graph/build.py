from __future__ import annotations

import os
import re
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4
from typing import Annotated, Any, Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, trim_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph, add_messages

from .reducers import watchlist_reducer

load_dotenv()


class WatchlyState(TypedDict, total=False):
    # Topic 2: default message reducer plus a custom watchlist reducer.
    messages: Annotated[list[BaseMessage], add_messages]
    watchlist: Annotated[list[dict[str, Any]], watchlist_reducer]
    user_id: str
    profile: dict[str, str]
    intent: Literal['recommend', 'add_watchlist', 'remove_watchlist', 'mark_watched', 'preferences', 'chat']
    trim_stats: dict[str, int]
    model_messages: list[BaseMessage]
    response: str


def classify(text: str) -> str:
    text = text.lower()
    if any(word in text for word in ('remove ', 'delete ', 'take off', 'unwatch')):
        return 'remove_watchlist'
    if any(word in text for word in ('add ', 'save ', 'watchlist')):
        return 'add_watchlist'
    if any(word in text for word in ('watched', 'finished', 'mark ')):
        return 'mark_watched'
    if any(word in text for word in ('i like ', 'i love ', 'netflix', 'genre', 'prefer ')):
        return 'preferences'
    if any(word in text for word in ('recommend', 'suggest', 'what should', 'movie', 'show', 'watch tonight')):
        return 'recommend'
    return 'chat'


def trim_history(state: WatchlyState) -> dict[str, Any]:
    messages = state.get('messages', [])
    token_counter = lambda values: sum(max(1, len(str(message.content)) // 4) for message in values)
    before_tokens = token_counter(messages)
    trimmed = trim_messages(messages, max_tokens=1200, token_counter=token_counter, strategy='last', start_on='human')
    return {
        'model_messages': trimmed,
        'trim_stats': {
            'messages_before': len(messages),
            'messages_sent': len(trimmed),
            'tokens_before': before_tokens,
            'tokens_sent': token_counter(trimmed),
            'token_budget': 1200,
        },
    }


def router(state: WatchlyState) -> dict[str, str]:
    latest = next((message.content for message in reversed(state['messages']) if isinstance(message, HumanMessage)), '')
    return {'intent': classify(str(latest))}


def route(state: WatchlyState) -> str:
    return state.get('intent', 'chat')


def _gemini_reply(prompt: str) -> str | None:
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        return None
    from google import genai
    client = genai.Client(api_key=key)
    try:
        response = client.models.generate_content(model=os.getenv('GEMINI_MODEL', 'gemini-3.6-flash'), contents=prompt)
        return response.text
    except Exception:
        return 'Gemini is temporarily unavailable. Please try your message again in a moment.'


def _latest_request(state: WatchlyState) -> str:
    messages = state.get('model_messages') or state.get('messages', [])
    return str(messages[-1].content) if messages else ''


def _clean_command(text: str, action: str) -> str:
    cleaned = re.sub(r'^\s*(?:okay|ok|sure|please|can you|could you)\s*[,!]?\s*', '', text, flags=re.IGNORECASE)
    return re.sub(rf'^\s*{action}\s+', '', cleaned, flags=re.IGNORECASE)


def _tmdb_search(title: str) -> dict[str, Any]:
    key = os.getenv('TMDB_API_KEY')
    if not key:
        return {}
    try:
        request = Request(
            f'https://api.themoviedb.org/3/search/multi?api_key={quote(key)}&query={quote(title)}',
            headers={'Accept': 'application/json'},
        )
        with urlopen(request, timeout=5) as response:
            results = __import__('json').load(response).get('results', [])
        match = next((item for item in results if item.get('media_type') in ('movie', 'tv')), {})
        return {
            'tmdb_id': match.get('id'),
            'media_type': 'tv' if match.get('media_type') == 'tv' else 'movie',
            'poster_path': match.get('poster_path'),
        }
    except Exception:
        return {}


def recommend(state: WatchlyState) -> dict[str, Any]:
    profile = state.get('profile', {})
    latest = _latest_request(state)
    tmdb_context = _tmdb_search(latest)
    prompt = f"You are Watchly, a concise movie and TV assistant. User preferences: {profile}. Request: {latest}. TMDB context: {tmdb_context}. Give 3 real, clearly formatted recommendations."
    remembered = profile.get('favorite_genre') or 'your saved preferences'
    reply = _gemini_reply(prompt) or f'I remember you like {remembered}. Add your Gemini API key to .env for live recommendations; the offline demo is still running.'
    return {'response': reply, 'messages': [AIMessage(content=reply)]}


def chat(state: WatchlyState) -> dict[str, Any]:
    latest = _latest_request(state)
    profile = state.get('profile', {})
    reply = _gemini_reply(f"You are Watchly, a helpful movie and TV assistant. Profile: {profile}. Reply briefly to: {latest}") or f'I can help with movie night. I remember: {profile.get("favorite_genre", "no saved genre yet")}. Add GEMINI_API_KEY to .env for live replies.'
    return {'response': reply, 'messages': [AIMessage(content=reply)]}


def add_to_watchlist(state: WatchlyState) -> dict[str, Any]:
    request = _latest_request(state)
    title = _clean_command(request, r'(?:add|save)')
    title = re.sub(r'\s+(?:to|on)\s+(?:my\s+)?watchlist\s*$', '', title, flags=re.IGNORECASE).strip(' .!') or 'Untitled movie'
    item = {'id': str(uuid4()), 'title': title, 'status': 'to_watch', 'media_type': 'movie', **_tmdb_search(title)}
    reply = f'Added {title} to your watchlist.'
    return {'watchlist': [item], 'response': reply, 'messages': [AIMessage(content=reply)]}


def remove_from_watchlist(state: WatchlyState) -> dict[str, Any]:
    request = _latest_request(state)
    title = _clean_command(request, r'(?:remove|delete)')
    title = re.sub(r'\s+(?:from|off)\s+(?:my\s+)?watchlist\s*$', '', title, flags=re.IGNORECASE).strip(' .!') or 'that title'
    reply = f'Removed {title} from your watchlist.'
    return {'watchlist': [{'_remove': True, 'title': title}], 'response': reply, 'messages': [AIMessage(content=reply)]}


def mark_watched(state: WatchlyState) -> dict[str, Any]:
    title = str(state['messages'][-1].content).replace('watched', '').replace('mark', '').strip(' .!')
    item = {'id': str(uuid4()), 'title': title or 'Selected title', 'status': 'watched'}
    reply = f'Marked {item["title"]} as watched.'
    return {'watchlist': [item], 'response': reply, 'messages': [AIMessage(content=reply)]}


def update_preferences(state: WatchlyState) -> dict[str, Any]:
    latest = _latest_request(state)
    profile = dict(state.get('profile', {}))
    lowered = latest.lower()
    if 'netflix' in lowered:
        profile['preferred_platform'] = 'Netflix'
    for genre in ('sci-fi', 'comedy', 'drama', 'horror', 'fantasy', 'thriller', 'romance'):
        if genre in lowered:
            profile['favorite_genre'] = genre
            break
    reply = f'Saved that preference. I will remember {profile.get("favorite_genre", "it")} for future recommendations.'
    return {'profile': profile, 'response': reply, 'messages': [AIMessage(content=reply)]}


def build_graph():
    builder = StateGraph(WatchlyState)
    builder.add_node('trim_history', trim_history)
    builder.add_node('router', router)
    builder.add_node('recommend', recommend)
    builder.add_node('add_to_watchlist', add_to_watchlist)
    builder.add_node('remove_from_watchlist', remove_from_watchlist)
    builder.add_node('mark_watched', mark_watched)
    builder.add_node('preferences', update_preferences)
    builder.add_node('chat', chat)
    builder.add_edge(START, 'trim_history')
    builder.add_edge('trim_history', 'router')
    builder.add_conditional_edges('router', route, {
        'recommend': 'recommend', 'add_watchlist': 'add_to_watchlist', 'remove_watchlist': 'remove_from_watchlist',
        'mark_watched': 'mark_watched', 'preferences': 'preferences', 'chat': 'chat'
    })
    for node in ('recommend', 'add_to_watchlist', 'remove_from_watchlist', 'mark_watched', 'preferences', 'chat'):
        builder.add_edge(node, END)
    return builder.compile(checkpointer=InMemorySaver())


watchly_graph = build_graph()
