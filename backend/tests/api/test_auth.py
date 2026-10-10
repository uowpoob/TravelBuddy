from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api import dependencies
from backend.app.api.v1.routes.auth import router
from backend.app.core.config import AuthSettings
from backend.app.core.security import verify_password
from backend.app.models import User
from backend.app.services import auth


@pytest.fixture
def auth_api(monkeypatch):
    """使用内存中的用户替代数据库，运行真实路由、密码和令牌逻辑。"""
    settings = AuthSettings(
        _env_file=None, AUTH_SECRET_KEY="auth-test-signing-secret-" * 3
    )
    users = {}
    session = MagicMock(spec=AsyncSession)

    async def insert(username, password_hash):
        if username in users:
            original = Exception("duplicate username")
            original.sqlstate = "23505"
            original.diag = SimpleNamespace(constraint_name="uq_users_username")
            raise IntegrityError("INSERT INTO users", {}, original)
        user = User(
            id=len(users) + 1,
            username=username,
            password_hash=password_hash,
            created_at=datetime.now(UTC),
        )
        users[username] = user
        return user

    repository = MagicMock()
    repository.insert = AsyncMock(side_effect=insert)
    repository.get_by_username = AsyncMock(side_effect=users.get)
    repository.get_by_id = AsyncMock(
        side_effect=lambda user_id: next(
            (user for user in users.values() if user.id == user_id), None
        )
    )
    monkeypatch.setattr(auth, "UserRepository", lambda session: repository)
    monkeypatch.setattr(dependencies, "UserRepository", lambda session: repository)

    async def get_session():
        yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[dependencies.get_session] = get_session
    app.dependency_overrides[dependencies.get_auth_settings] = lambda: settings
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, users=users, settings=settings)


def test_register_login_and_current_user(auth_api):
    credentials = {"username": " demo_user ", "password": "test-password"}
    response = auth_api.client.post("/api/v1/auth/register", json=credentials)
    assert response.status_code == 201
    public_user = response.json()
    assert public_user["username"] == "demo_user"
    assert set(public_user) == {"id", "username", "created_at"}
    password_hash = auth_api.users["demo_user"].password_hash
    assert password_hash != credentials["password"]
    assert verify_password(credentials["password"], password_hash)

    response = auth_api.client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200
    login = response.json()
    assert login["token_type"] == "bearer"
    assert login["expires_in"] == 3600
    assert login["user"] == public_user
    response = auth_api.client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json() == public_user


def test_duplicate_registration_returns_conflict(auth_api):
    credentials = {"username": "demo_user", "password": "test-password"}
    assert (
        auth_api.client.post("/api/v1/auth/register", json=credentials).status_code
        == 201
    )
    response = auth_api.client.post("/api/v1/auth/register", json=credentials)
    assert response.status_code == 409
    assert len(auth_api.users) == 1


@pytest.mark.parametrize("username", ["demo_user", "missing_user"])
def test_wrong_password_or_missing_user_returns_unauthorized(auth_api, username):
    auth_api.client.post(
        "/api/v1/auth/register",
        json={"username": "demo_user", "password": "test-password"},
    )
    response = auth_api.client.post(
        "/api/v1/auth/login", json={"username": username, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "账号或密码错误。"


@pytest.mark.parametrize(
    ("claims", "algorithm", "other_key"),
    [
        ({"exp": datetime.now(UTC) - timedelta(minutes=1)}, "HS256", False),
        ({"exp": None}, "HS256", False),
        ({"sub": "not-a-user-id"}, "HS256", False),
        ({"sub": str(2**63)}, "HS256", False),
        ({"sub": "0"}, "HS256", False),
        ({"iss": "another-app"}, "HS256", False),
        ({"aud": "another-api"}, "HS256", False),
        ({}, "HS512", False),
        ({}, "HS256", True),
    ],
)
def test_invalid_tokens_return_unauthorized(auth_api, claims, algorithm, other_key):
    payload = {
        "sub": "1",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": "travelbuddy",
        "aud": "travelbuddy-api",
        **claims,
    }
    if payload["exp"] is None:
        del payload["exp"]
    key = (
        "another-test-signing-secret-" * 3
        if other_key
        else auth_api.settings.AUTH_SECRET_KEY.get_secret_value()
    )
    token = jwt.encode(payload, key, algorithm=algorithm)
    auth_api.users["demo_user"] = User(id=1, username="demo_user")
    response = auth_api.client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_missing_token_or_deleted_user_returns_unauthorized(auth_api):
    assert auth_api.client.get("/api/v1/auth/me").status_code == 401
    credentials = {"username": "demo_user", "password": "test-password"}
    auth_api.client.post("/api/v1/auth/register", json=credentials)
    token = auth_api.client.post("/api/v1/auth/login", json=credentials).json()[
        "access_token"
    ]
    auth_api.users.clear()
    response = auth_api.client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
