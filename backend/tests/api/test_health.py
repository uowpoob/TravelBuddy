from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app.main import app


def test_liveness_and_missing_database():
    with TestClient(app) as client:
        assert client.get("/health").json() == {
            "status": "ok",
            "service": "TravelBuddy",
        }
        engine = app.state.db_engine
        app.state.db_engine = None
        try:
            response = client.get("/health/db")
            assert response.status_code == 503
            assert response.json()["database"] == "not_configured"
        finally:
            app.state.db_engine = engine


def test_database_failure_does_not_leak_credentials():
    with TestClient(app) as client:
        engine = app.state.db_engine
        broken = MagicMock()
        broken.connect.side_effect = OperationalError(
            "SELECT 1", {}, Exception("password=do-not-leak")
        )
        app.state.db_engine = broken
        try:
            response = client.get("/health/db")
            assert response.status_code == 503
            assert response.json() == {"status": "error", "database": "unavailable"}
            assert "do-not-leak" not in response.text
        finally:
            app.state.db_engine = engine


def test_database_health_executes_query():
    with TestClient(app) as client:
        engine = app.state.db_engine
        connection = AsyncMock()
        mocked = MagicMock()
        mocked.connect.return_value.__aenter__ = AsyncMock(return_value=connection)
        mocked.connect.return_value.__aexit__ = AsyncMock(return_value=None)
        app.state.db_engine = mocked
        try:
            response = client.get("/health/db")
            assert response.status_code == 200
            assert response.json()["database"] == "postgresql"
            connection.execute.assert_awaited_once()
        finally:
            app.state.db_engine = engine
