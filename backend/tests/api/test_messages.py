from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from psycopg import OperationalError as CheckpointError
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api import dependencies
from backend.app.api.router import router
from backend.app.api.v1.routes.conversations import get_chat_service
from backend.app.core.config import AuthSettings
from backend.app.core.security import create_access_token
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.clarify import ClarifyNode
from backend.app.graph.nodes.confirm import ConfirmNode
from backend.app.graph.nodes.save import SaveNode
from backend.app.graph.state import TripState
from backend.app.models import Conversation, User
from backend.app.services.itineraries import SavedItineraryResult
from backend.app.services.messages import ConversationChatService


@pytest.fixture
def message_api(confirmed_trip_state, monkeypatch):
    user = User(id=41, username="message_user")
    timestamp = datetime.now(UTC)
    conversation = Conversation(
        id=str(uuid4()),
        user_id=user.id,
        title="杭州旅行",
        created_at=timestamp,
        updated_at=timestamp,
    )
    settings = AuthSettings(
        _env_file=None, AUTH_SECRET_KEY="message-test-signing-secret-" * 3
    )
    session = MagicMock(spec=AsyncSession)
    save_session = MagicMock(spec=AsyncSession)
    save_session.in_transaction.return_value = False
    save_session.execute.return_value.rowcount = 1
    factory = MagicMock(return_value=save_session)
    save_session.__aenter__.return_value = save_session
    save = AsyncMock(return_value=SavedItineraryResult(123, 1))
    monkeypatch.setattr("backend.app.graph.nodes.save.save_confirmed_itinerary", save)
    api = SimpleNamespace(
        session=session,
        save_session=save_session,
        factory=factory,
        save=save,
        user=user,
        conversation=conversation,
        busy=False,
        itineraries={},
    )

    async def save_itinerary(*args, **kwargs):
        api.itineraries[123] = SimpleNamespace(id=123, version=1)
        return SavedItineraryResult(123, 1)

    save.side_effect = save_itinerary

    async def get_user(*args):
        session.in_transaction.return_value = True
        return user

    async def scalar(statement):
        session.in_transaction.return_value = True
        if "pg_try_advisory_xact_lock" in str(statement):
            return not api.busy
        params = statement.compile().params
        assert params["user_id_1"] == user.id
        if "FROM itineraries" in str(statement):
            return api.itineraries.get(params["id_1"])
        return conversation if params["id_1"] == conversation.id else None

    async def finish():
        session.in_transaction.return_value = False

    session.get.side_effect = get_user
    session.scalar.side_effect = scalar
    session.commit.side_effect = finish
    session.rollback.side_effect = finish

    def prepare(state):
        humans = [m for m in state["messages"] if isinstance(m, HumanMessage)]
        if len(humans) == 1:
            return {
                "clarification_question": "几个人出行？",
                "missing_fields": ["travelers"],
            }
        return {**confirmed_trip_state, "confirmed": False, "missing_fields": []}

    builder = StateGraph(TripState, context_schema=TravelBuddyContext)
    builder.add_node("prepare", prepare)
    builder.add_node("clarify", ClarifyNode())
    builder.add_node("confirm", ConfirmNode())
    builder.add_node("save", SaveNode())
    builder.add_edge(START, "prepare")
    builder.add_conditional_edges(
        "prepare", lambda state: "clarify" if state["missing_fields"] else "confirm"
    )
    builder.add_edge("clarify", "prepare")
    builder.add_conditional_edges(
        "confirm", lambda state: "save" if state["confirmed"] else "prepare"
    )
    builder.add_edge("save", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    async def get_session():
        yield session

    app = FastAPI()
    app.include_router(router)
    app.state.trip_graph = graph
    app.state.session_factory = factory
    app.dependency_overrides[dependencies.get_session] = get_session
    app.dependency_overrides[dependencies.get_auth_settings] = lambda: settings
    api.app = app
    api.graph = graph
    api.config = {"configurable": {"thread_id": conversation.id}}
    api.headers = {"Authorization": f"Bearer {create_access_token(user.id, settings)}"}
    api.path = f"/api/v1/conversations/{conversation.id}/messages"
    with TestClient(app) as client:
        api.client = client
        yield api


def send(api, content=None, *, retry=False):
    payload = {"retry": True} if retry else {"content": content}
    return api.client.post(api.path, headers=api.headers, json=payload)


def read(api, **params):
    return api.client.get(api.path, headers=api.headers, params=params)


def test_new_conversation_has_empty_history_without_invoking_graph(message_api):
    api = message_api
    response = read(api)
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == api.conversation.id
    assert body["items"] == []
    assert (body["total"], body["offset"], body["limit"]) == (0, 0, 50)
    assert body["status"] == "completed"
    assert body["interrupt"] is None
    api.factory.assert_not_called()
    api.session.execute.assert_not_awaited()
    api.session.commit.assert_not_awaited()


def test_send_without_model_title_does_not_generate_a_title(message_api):
    api = message_api
    response = send(api, "想去杭州。请帮我规划")
    assert response.status_code == 200
    assert response.json()["title"] is None
    statement = api.session.execute.await_args.args[0]
    assert "title" not in statement.compile().params
    api.session.execute.reset_mock()
    followup = send(api, "2个人")
    assert followup.status_code == 200
    # 后续回答不能把首条消息概括覆盖成“2个人”。
    assert "title" not in api.session.execute.await_args.args[0].compile().params


def test_send_clarify_confirm_save_and_reload_with_stable_question_ids(message_api):
    api = message_api
    response = send(api, " 想去杭州 ")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    first = response.json()
    assert first["status"] == "waiting_clarification"
    assert [(m["role"], m["content"]) for m in first["items"]] == [
        ("user", "想去杭州"),
    ]
    assert first["interrupt"]["missing_fields"] == ["travelers"]
    assert first["interrupt"]["question"] == "几个人出行？"
    assert read(api).json()["items"] == first["items"]

    second = send(api, "2 人").json()
    assert second["status"] == "waiting_approval"
    assert [(m["role"]) for m in second["items"]] == ["assistant", "user"]
    assert [m["content"] for m in second["items"]] == ["几个人出行？", "2 人"]
    assert second["interrupt"]["type"] == "confirm"
    assert "测试景点" in second["interrupt"]["summary"]
    assert second["interrupt"]["itinerary"]["days"][0]["day"] == 1
    api.save.assert_not_awaited()

    third = send(api, "确认").json()
    assert third["status"] == "completed"
    assert third["interrupt"] is None
    assert (third["saved_itinerary_id"], third["saved_itinerary_version"]) == (123, 1)
    assert [m["role"] for m in third["items"]] == ["assistant", "user"]
    assert "测试景点" in third["items"][0]["content"]
    assert third["items"][1]["content"] == "确认"
    all_items = first["items"] + second["items"] + third["items"]
    assert read(api).json()["items"] == all_items
    assert len({m["id"] for m in all_items}) == 5
    assert api.save.await_args.kwargs["user_id"] == api.user.id
    assert api.save.await_args.kwargs["conversation_id"] == api.conversation.id
    assert api.save.await_args.args[0] is api.save_session
    assert api.save_session is not api.session
    assert api.session.commit.await_count == 3
    # The saved-reference lookup starts a read transaction after the commit;
    # send_message rolls it back to release the connection before returning.
    api.session.rollback.assert_awaited_once()
    assert "updated_at=clock_timestamp()" in str(api.session.execute.await_args.args[0])


def test_confirmation_modification_runs_another_turn_without_saving(message_api):
    api = message_api
    send(api, "去杭州")
    send(api, "2人")
    response = send(api, "下午改成室内活动")
    assert response.status_code == 200
    assert response.json()["status"] == "waiting_approval"
    assert response.json()["items"][-1]["content"] == "下午改成室内活动"
    api.save.assert_not_awaited()


def test_filter_internal_messages_and_paginate_chronologically(message_api):
    api = message_api
    messages = [
        SystemMessage(content="private system prompt"),
        HumanMessage(content="用户消息"),
        AIMessage(
            content="private tool call",
            tool_calls=[{"id": "call-1", "name": "private_tool", "args": {}}],
        ),
        ToolMessage(content="private tool result", tool_call_id="call-1"),
        AIMessage(
            content=[
                {"type": "reasoning", "reasoning": "private reasoning"},
                {"type": "text", "text": "助手消息"},
            ]
        ),
        AIMessage(content=""),
        HumanMessage(content="第二条用户消息"),
    ]
    api.client.portal.call(
        api.graph.aupdate_state, api.config, {"messages": messages}, "save"
    )
    response = read(api, offset=1, limit=1)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert (body["offset"], body["limit"]) == (1, 1)
    assert body["items"][0]["content"] == "助手消息"
    assert "private" not in response.text
    assert read(api, offset=10).json()["items"] == []


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("authorization", [None, "Bearer invalid"])
def test_messages_require_authentication(message_api, method, authorization):
    api = message_api
    response = getattr(api.client, method)(
        api.path,
        **{
            "headers": {"Authorization": authorization} if authorization else {},
            **({"json": {"content": "消息"}} if method == "post" else {}),
        },
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    api.session.scalar.assert_not_awaited()


@pytest.mark.parametrize("method", ["get", "post"])
def test_unknown_or_foreign_conversations_do_not_read_checkpoint(message_api, method):
    api = message_api
    api.app.state.trip_graph = MagicMock()
    response = getattr(api.client, method)(
        f"/api/v1/conversations/{uuid4()}/messages",
        headers=api.headers,
        **({"json": {"content": "消息"}} if method == "post" else {}),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "会话不存在。"}
    api.app.state.trip_graph.aget_state.assert_not_called()
    api.app.state.trip_graph.ainvoke.assert_not_called()
    api.factory.assert_not_called()


@pytest.mark.parametrize("method", ["get", "post"])
def test_unavailable_graph_returns_503_after_ownership_check(message_api, method):
    api = message_api
    api.app.state.trip_graph = None
    response = getattr(api.client, method)(
        api.path,
        headers=api.headers,
        **({"json": {"content": "消息"}} if method == "post" else {}),
    )
    assert response.status_code == 503
    assert api.session.scalar.await_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"content": None},
        {"content": ""},
        {"content": " \n\t "},
        {"content": 123},
        {"content": "a" * 10001},
        {"content": "消息", "retry": True},
        {"retry": "true"},
    ],
)
def test_invalid_message_does_not_execute_or_lock(message_api, payload):
    api = message_api
    response = api.client.post(api.path, headers=api.headers, json=payload)
    assert response.status_code == 422
    api.session.scalar.assert_not_awaited()
    api.factory.assert_not_called()


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": 101},
        {"limit": "invalid"},
    ],
)
def test_invalid_pagination_does_not_read_checkpoint(message_api, params):
    api = message_api
    assert read(api, **params).status_code == 422
    api.session.scalar.assert_not_awaited()


@pytest.mark.parametrize("method", ["get", "post"])
def test_uuid_validation_and_normalization(message_api, method):
    api = message_api
    kwargs = {"headers": api.headers}
    if method == "post":
        kwargs["json"] = {"content": "消息"}
    assert (
        getattr(api.client, method)(
            "/api/v1/conversations/not-a-uuid/messages", **kwargs
        ).status_code
        == 422
    )
    response = getattr(api.client, method)(
        api.path.replace(api.conversation.id, api.conversation.id.upper()), **kwargs
    )
    assert response.status_code == 200
    assert response.json()["conversation_id"] == api.conversation.id


def test_concurrent_send_rejected_without_invoking_graph(message_api):
    api = message_api
    api.busy = True
    graph = MagicMock()
    api.app.state.trip_graph = graph
    response = send(api, "消息")
    assert response.status_code == 409
    graph.aget_state.assert_not_called()
    graph.ainvoke.assert_not_called()
    api.session.commit.assert_not_awaited()
    api.session.rollback.assert_awaited_once()


@pytest.mark.parametrize("waiting", [False, True])
def test_retry_rejected_without_failed_steps_or_while_waiting_for_answer(
    message_api, waiting
):
    api = message_api
    if waiting:
        send(api, "去杭州")
    api.session.commit.reset_mock()
    response = send(api, retry=True)
    assert response.status_code == 409
    api.session.commit.assert_not_awaited()


def test_failed_graph_is_readable_and_retry_does_not_duplicate_user_message(
    message_api,
):
    api = message_api
    node = AsyncMock(side_effect=RuntimeError("private model error"))
    builder = StateGraph(TripState)
    builder.add_node("reply", node)
    builder.add_edge(START, "reply")
    builder.add_edge("reply", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    api.app.state.trip_graph = graph
    response = send(api, "消息")
    assert response.status_code == 502
    assert "private" not in response.text
    api.session.rollback.assert_awaited_once()
    history = read(api).json()
    assert history["status"] == "pending"
    assert [m["content"] for m in history["items"]] == ["消息"]
    assert send(api, "其他消息").status_code == 409
    node.side_effect = None
    node.return_value = {"messages": [AIMessage(content="回复成功")]}
    response = send(api, retry=True)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert [m["content"] for m in response.json()["items"]] == ["回复成功"]
    assert read(api).json()["total"] == 2


@pytest.mark.parametrize("method", ["get", "post"])
def test_database_error_returns_safe_503(message_api, method):
    api = message_api
    api.session.scalar.side_effect = OperationalError(
        "SELECT", {}, Exception("private db")
    )
    response = getattr(api.client, method)(
        api.path,
        headers=api.headers,
        **({"json": {"content": "消息"}} if method == "post" else {}),
    )
    assert response.status_code == 503
    assert "private" not in response.text


@pytest.mark.parametrize(
    "error, status",
    [
        (CheckpointError("private checkpoint"), 503),
        (RuntimeError("private graph"), 502),
        (TimeoutError("private timeout"), 504),
    ],
)
@pytest.mark.parametrize("method", ["get", "post"])
def test_checkpoint_failure_and_timeout_are_sanitized(
    message_api, error, status, method
):
    api = message_api
    graph = MagicMock()
    graph.aget_state = AsyncMock(side_effect=error)
    api.app.state.trip_graph = graph
    response = getattr(api.client, method)(
        api.path,
        headers=api.headers,
        **({"json": {"content": "消息"}} if method == "post" else {}),
    )
    assert response.status_code == status
    assert "private" not in response.text
    if method == "post":
        api.session.rollback.assert_awaited_once()


def test_execution_timeout_releases_lock_and_allows_retry(message_api):
    import asyncio

    api = message_api

    async def slow_reply(state):
        await asyncio.sleep(1)
        return {"messages": [AIMessage(content="已恢复")]}

    builder = StateGraph(TripState)
    builder.add_node("reply", slow_reply)
    builder.add_edge(START, "reply")
    builder.add_edge("reply", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    api.app.state.trip_graph = graph
    api.app.dependency_overrides[get_chat_service] = lambda: ConversationChatService(
        graph, api.factory, timeout=0.1
    )
    assert send(api, "消息").status_code == 504
    api.session.rollback.assert_awaited_once()
    assert read(api).json()["status"] == "pending"
    api.app.dependency_overrides.pop(get_chat_service)
    assert send(api, retry=True).status_code == 200
    assert read(api).json()["total"] == 2
