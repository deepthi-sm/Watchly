from langchain_core.messages import HumanMessage

from graph.build import classify, route, watchly_graph
from graph.reducers import watchlist_reducer


def test_router_branches_by_intent():
    assert classify('recommend a sci-fi movie') == 'recommend'
    assert route({'intent': 'add_watchlist'}) == 'add_watchlist'


def test_watchlist_reducer_updates_without_duplicates():
    current = [{'title': 'Dune', 'status': 'to_watch'}]
    assert watchlist_reducer(current, [{'title': 'Dune', 'status': 'watched'}]) == [{'title': 'Dune', 'status': 'watched'}]


def test_watchlist_reducer_removes_by_title():
    current = [{'title': 'Dune', 'status': 'to_watch'}, {'title': 'Arrival', 'status': 'to_watch'}]
    assert watchlist_reducer(current, [{'_remove': True, 'title': 'Dune'}]) == [{'title': 'Arrival', 'status': 'to_watch'}]


def test_graph_records_checkpointed_messages():
    result = watchly_graph.invoke(
        {'messages': [HumanMessage(content='I prefer comedy')]},
        {'configurable': {'thread_id': 'pytest-thread'}},
    )
    assert result['intent'] == 'preferences'
    assert result['profile']['favorite_genre'] == 'comedy'
    assert result['trim_stats']['messages_sent'] == 1


def test_add_command_removes_polite_prefix():
    result = watchly_graph.invoke(
        {'messages': [HumanMessage(content='okay, add hannibal')]},
        {'configurable': {'thread_id': 'pytest-add-command'}},
    )
    assert result['intent'] == 'add_watchlist'
    assert result['watchlist'][-1]['title'] == 'hannibal'