from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api import dependencies
from backend.app.api.router import router
from backend.app.core.config import AuthSettings
from backend.app.core.security import create_access_token
from backend.app.models import Conversation, User


@pytest.fixture
def conversation_api():
    """运行真实鉴权、路由、服务和仓储，用模拟 session 替代数据库连接。"""
    settings = AuthSettings(
        _env_file=None, AUTH_SECRET_KEY="conversation-test-signing-secret-" * 3
    )
    user = User(id=41, username="conversation_user")
    session = MagicMock(spec=AsyncSession)
    session.scalar.return_value = None
    session.get = AsyncMock(
        side_effect=lambda model, user_id: user if user_id == user.id else None
    )
    records = []
    session.add.side_effect = records.append

    async def flush():
        record = records[-1]
        record.id = str(uuid4())
        record.created_at = record.updated_at = datetime.now(UTC)

    session.flush.side_effect = flush

    async def get_session():
        yield session

    app = FastAPI()
    app.include_router(router)
    app.state.trip_graph = SimpleNamespace(
        aget_state=AsyncMock(
            return_value=SimpleNamespace(values={}, interrupts=(), next=())
        )
    )
    app.dependency_overrides[dependencies.get_session] = get_session
    app.dependency_overrides[dependencies.get_auth_settings] = lambda: settings
    headers = {"Authorization": f"Bearer {create_access_token(user.id, settings)}"}
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client, session=session, user=user, records=records, headers=headers
        )


def test_create_conversation_uses_authenticated_owner_and_trims_title(conversation_api):
    api = conversation_api
    response = api.client.post(
        "/api/v1/conversations",
        headers=api.headers,
        json={"title": " 杭州周末游 ", "user_id": 999},
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "title", "created_at", "updated_at", "reused"}
    assert body["reused"] is False
    assert str(UUID(body["id"])) == body["id"]
    assert body["title"] == "杭州周末游"
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
    assert body["updated_at"] == body["created_at"]
    assert len(api.records) == 1
    assert isinstance(api.records[0], Conversation)
    assert api.records[0].user_id == api.user.id
    api.session.get.assert_awaited_once_with(User, api.user.id)
    api.session.commit.assert_awaited_once()
    api.session.rollback.assert_not_awaited()


def test_create_conversation_with_default_title(conversation_api):
    api = conversation_api
    response = api.client.post("/api/v1/conversations", headers=api.headers, json={})
    assert response.status_code == 201
    assert response.json()["title"] == "新旅行"
    api.session.commit.assert_awaited_once()


@pytest.mark.parametrize("title", ["", " \t\n ", "a" * 101, None, 123])
def test_invalid_title_does_not_create_conversation(conversation_api, title):
    api = conversation_api
    response = api.client.post(
        "/api/v1/conversations", headers=api.headers, json={"title": title}
    )
    assert response.status_code == 422
    api.session.add.assert_not_called()
    api.session.commit.assert_not_awaited()


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-token"])
def test_missing_or_invalid_token_does_not_create_conversation(
    conversation_api, authorization
):
    api = conversation_api
    headers = {"Authorization": authorization} if authorization else {}
    response = api.client.post("/api/v1/conversations", headers=headers, json={})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    api.session.add.assert_not_called()
    api.session.commit.assert_not_awaited()


def test_deleted_user_does_not_create_conversation(conversation_api):
    api = conversation_api
    api.session.get.side_effect = None
    api.session.get.return_value = None
    response = api.client.post("/api/v1/conversations", headers=api.headers, json={})
    assert response.status_code == 401
    api.session.add.assert_not_called()
    api.session.commit.assert_not_awaited()


@pytest.mark.parametrize("stage", ["flush", "commit"])
def test_database_failure_rolls_back_and_returns_service_unavailable(
    conversation_api, stage
):
    api = conversation_api
    getattr(api.session, stage).side_effect = OperationalError(
        "INSERT INTO conversations", {}, Exception("private database error")
    )
    response = api.client.post("/api/v1/conversations", headers=api.headers, json={})
    assert response.status_code == 503
    assert response.json() == {"detail": "数据库暂时不可用，请稍后重试。"}
    assert "private database error" not in response.text
    api.session.rollback.assert_awaited_once()
    if stage == "flush":
        api.session.commit.assert_not_awaited()


@pytest.fixture
def conversation_queries(conversation_api):
    """在内存 SQLite 上执行真实仓储查询，验证归属、排序和分页。"""
    api = conversation_api
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def add_postgres_trim(connection, _):
        connection.create_function("btrim", 1, str.strip)

    try:
        Conversation.__table__.create(engine)
        with Session(engine, expire_on_commit=False) as query_session:
            api.session.scalars.side_effect = query_session.scalars
            api.session.scalar.side_effect = query_session.scalar

            def seed(
                *,
                title="测试会话",
                user_id=None,
                updated_at=None,
                record_id=None,
                planning_progress=None,
            ):
                timestamp = updated_at or datetime.now(UTC)
                record = Conversation(
                    id=record_id or str(uuid4()),
                    user_id=api.user.id if user_id is None else user_id,
                    title=title,
                    planning_progress=planning_progress,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                query_session.add(record)
                query_session.commit()
                return record

            api.seed = seed
            yield api
    finally:
        engine.dispose()


def test_list_returns_empty_array_for_user_without_conversations(conversation_queries):
    api = conversation_queries
    api.seed(user_id=999)
    response = api.client.get("/api/v1/conversations", headers=api.headers)
    assert response.status_code == 200
    assert response.json() == []
    api.session.commit.assert_not_awaited()


def test_create_reuses_owned_empty_conversation_even_with_custom_title(
    conversation_queries,
):
    api = conversation_queries
    existing = api.seed(title="自定义旅行想法")
    api.seed(user_id=999, title="其他人的空会话")
    response = api.client.post("/api/v1/conversations", headers=api.headers, json={})
    assert response.status_code == 200
    assert response.json()["reused"] is True
    assert response.json()["id"] == existing.id
    assert response.json()["title"] == "自定义旅行想法"
    api.session.add.assert_not_called()
    api.session.commit.assert_awaited_once()


@pytest.mark.parametrize(
    "status", ["running", "failed", "waiting_clarification", "completed"]
)
def test_create_allows_new_conversation_after_first_send(conversation_queries, status):
    api = conversation_queries
    existing = api.seed(title="新旅行", planning_progress={"status": status})
    response = api.client.post("/api/v1/conversations", headers=api.headers, json={})
    assert response.status_code == 201
    assert response.json()["reused"] is False
    assert response.json()["id"] != existing.id
    api.session.add.assert_called_once()


def test_create_checks_empty_conversations_beyond_first_list_page(conversation_queries):
    api = conversation_queries
    timestamp = datetime(2026, 10, 8, tzinfo=UTC)
    empty = api.seed(updated_at=timestamp)
    for number in range(25):
        api.seed(
            updated_at=timestamp + timedelta(hours=number + 1),
            planning_progress={"status": "completed"},
        )
    response = api.client.post("/api/v1/conversations", headers=api.headers, json={})
    assert response.status_code == 200
    assert response.json()["id"] == empty.id
    api.session.add.assert_not_called()


def test_other_users_empty_conversation_does_not_prevent_creation(conversation_queries):
    api = conversation_queries
    api.seed(user_id=999)
    response = api.client.post("/api/v1/conversations", headers=api.headers, json={})
    assert response.status_code == 201
    assert response.json()["reused"] is False


def test_list_filters_owner_before_sorting_and_pagination(conversation_queries):
    api = conversation_queries
    timestamp = datetime(2026, 10, 8, tzinfo=UTC)
    api.seed(title="较早的会话", updated_at=timestamp)
    api.seed(title="最新的会话", updated_at=timestamp + timedelta(hours=2))
    api.seed(title="中间的会话", updated_at=timestamp + timedelta(hours=1))
    api.seed(title="其他用户", user_id=999, updated_at=timestamp + timedelta(hours=3))

    response = api.client.get("/api/v1/conversations", headers=api.headers)
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == [
        "最新的会话",
        "中间的会话",
        "较早的会话",
    ]
    response = api.client.get(
        "/api/v1/conversations",
        headers=api.headers,
        params={"offset": 1, "limit": 1, "user_id": 999},
    )
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["中间的会话"]
    response = api.client.get(
        "/api/v1/conversations", headers=api.headers, params={"offset": 3}
    )
    assert response.json() == []
    api.session.commit.assert_not_awaited()


def test_list_has_stable_order_when_update_times_match(conversation_queries):
    api = conversation_queries
    timestamp = datetime(2026, 10, 8, tzinfo=UTC)
    for number in (2, 1, 3):
        api.seed(
            record_id=f"aaaaaaaa-0000-0000-0000-{number:012x}", updated_at=timestamp
        )
    first_page = api.client.get(
        "/api/v1/conversations", headers=api.headers, params={"limit": 2}
    ).json()
    second_page = api.client.get(
        "/api/v1/conversations",
        headers=api.headers,
        params={"limit": 2, "offset": 2},
    ).json()
    assert [item["id"] for item in first_page + second_page] == [
        f"aaaaaaaa-0000-0000-0000-{number:012x}" for number in (3, 2, 1)
    ]


def test_list_defaults_to_twenty_items_and_accepts_maximum_limit(conversation_queries):
    api = conversation_queries
    for _ in range(25):
        api.seed()
    response = api.client.get("/api/v1/conversations", headers=api.headers)
    assert response.status_code == 200
    assert len(response.json()) == 20
    response = api.client.get(
        "/api/v1/conversations", headers=api.headers, params={"limit": 100}
    )
    assert response.status_code == 200
    assert len(response.json()) == 25


@pytest.mark.parametrize(
    "params", [{"offset": -1}, {"limit": 0}, {"limit": 101}, {"offset": "invalid"}]
)
def test_invalid_pagination_returns_validation_error(conversation_queries, params):
    api = conversation_queries
    response = api.client.get(
        "/api/v1/conversations", headers=api.headers, params=params
    )
    assert response.status_code == 422
    api.session.scalars.assert_not_awaited()


def test_get_returns_owned_conversation_and_normalizes_uuid(conversation_queries):
    api = conversation_queries
    record = api.seed(title="杭州周末游")
    response = api.client.get(
        f"/api/v1/conversations/{record.id.upper()}", headers=api.headers
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "title", "created_at", "updated_at"}
    assert body["id"] == record.id
    assert body["title"] == record.title
    api.session.commit.assert_not_awaited()


def test_get_hides_other_users_conversation_as_not_found(conversation_queries):
    api = conversation_queries
    other = api.seed(user_id=999)
    for conversation_id in (other.id, str(uuid4())):
        response = api.client.get(
            f"/api/v1/conversations/{conversation_id}", headers=api.headers
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "会话不存在。"}


def test_get_invalid_uuid_returns_validation_error(conversation_queries):
    api = conversation_queries
    response = api.client.get("/api/v1/conversations/not-a-uuid", headers=api.headers)
    assert response.status_code == 422
    api.session.scalar.assert_not_awaited()


@pytest.mark.parametrize("detail", [False, True])
@pytest.mark.parametrize("authorization", [None, "Bearer invalid-token"])
def test_reads_require_authentication(conversation_queries, detail, authorization):
    api = conversation_queries
    path = "/api/v1/conversations"
    if detail:
        path += f"/{api.seed().id}"
    headers = {"Authorization": authorization} if authorization else {}
    response = api.client.get(path, headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    api.session.scalar.assert_not_awaited()
    api.session.scalars.assert_not_awaited()


@pytest.mark.parametrize("detail", [False, True])
def test_read_database_failure_returns_service_unavailable(
    conversation_queries, detail
):
    api = conversation_queries
    method = api.session.scalar if detail else api.session.scalars
    method.side_effect = OperationalError(
        "SELECT conversations", {}, Exception("private database error")
    )
    path = "/api/v1/conversations"
    if detail:
        path += f"/{uuid4()}"
    response = api.client.get(path, headers=api.headers)
    assert response.status_code == 503
    assert response.json() == {"detail": "数据库暂时不可用，请稍后重试。"}
    assert "private database error" not in response.text
    api.session.commit.assert_not_awaited()
