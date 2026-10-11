from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from graph.build import watchly_graph

app = FastAPI(title='Watchly API', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:4200', 'http://127.0.0.1:4200'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

threads: dict[str, list[dict]] = {}
watchlists: dict[str, list[dict]] = {}
profiles: dict[str, dict] = {}


class ChatRequest(BaseModel):
    user_id: str = 'local-demo-user'
    thread_id: str
    message: str = Field(min_length=1, max_length=4000)


class WatchlistRequest(BaseModel):
    user_id: str = 'local-demo-user'
    title: str
    tmdb_id: int | None = None
    media_type: str = 'movie'
    poster_path: str | None = None


class StatusRequest(BaseModel):
    status: str


@app.get('/health')
def health(): return {'status': 'ok'}


@app.get('/')
def home():
    return {'name': 'Watchly API', 'status': 'running', 'docs': '/docs', 'frontend': 'http://127.0.0.1:4200'}


@app.get('/graph/diagram')
def graph_diagram():
    graph = watchly_graph.get_graph()
    try:
        diagram = graph.draw_ascii()
    except Exception:
        diagram = graph.draw_mermaid()
    return {'mermaid': diagram}


@app.get('/memory')
def memory(user_id: str = 'local-demo-user'):
    return {'profile': profiles.get(user_id, {}), 'shortTerm': 'LangGraph checkpoint per thread', 'longTerm': 'Profile store shared across threads'}


@app.get('/threads')
def list_threads(user_id: str = 'local-demo-user'): return threads.get(user_id, [])


@app.post('/threads')
def create_thread(user_id: str = 'local-demo-user'):
    thread = {'id': str(uuid4()), 'title': 'New movie chat'}
    threads.setdefault(user_id, []).insert(0, thread)
    return thread


@app.get('/threads/{thread_id}/messages')
def thread_messages(thread_id: str):
    state = watchly_graph.get_state({'configurable': {'thread_id': thread_id}})
    messages = state.values.get('messages', []) if state else []
    return [{'role': 'user' if isinstance(message, HumanMessage) else 'assistant', 'content': str(message.content)} for message in messages]


@app.post('/chat/message')
def send_message(payload: ChatRequest):
    result = watchly_graph.invoke(
        {'messages': [HumanMessage(content=payload.message)], 'user_id': payload.user_id,
         'profile': profiles.get(payload.user_id, {}), 'watchlist': watchlists.get(payload.user_id, [])},
        {'configurable': {'thread_id': payload.thread_id}}
    )
    watchlists[payload.user_id] = result.get('watchlist', watchlists.get(payload.user_id, []))
    profiles[payload.user_id] = result.get('profile', profiles.get(payload.user_id, {}))
    return {'reply': result['response'], 'trimStats': result['trim_stats'], 'intent': result['intent'], 'watchlist': watchlists[payload.user_id], 'profile': profiles[payload.user_id]}


@app.get('/watchlist')
def list_watchlist(user_id: str = 'local-demo-user'): return watchlists.get(user_id, [])


@app.post('/watchlist')
def add_watchlist(payload: WatchlistRequest):
    item = {'id': str(uuid4()), **payload.model_dump(), 'status': 'to_watch'}
    items = watchlists.setdefault(payload.user_id, [])
    if any(existing.get('tmdb_id') == item['tmdb_id'] and item['tmdb_id'] is not None for existing in items):
        raise HTTPException(409, 'This title is already on the watchlist.')
    items.append(item)
    return item


@app.patch('/watchlist/{item_id}')
def change_status(item_id: str, payload: StatusRequest, user_id: str = 'local-demo-user'):
    for item in watchlists.get(user_id, []):
        if item['id'] == item_id:
            item['status'] = payload.status
            return item
    raise HTTPException(404, 'Watchlist item not found.')
