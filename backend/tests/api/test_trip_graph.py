from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.memory import InMemorySaver
from psycopg import OperationalError
from pydantic import SecretStr

from backend.app import lifespan as lifespan_module
from backend.app.api.dependencies import get_trip_graph


@pytest.fixture
def runtime_resources(monkeypatch):
    settings = SimpleNamespace(
        DEEPSEEK_API_KEY="test-key",
        DEEPSEEK_BASE_URL="https://example.invalid",
        DEEPSEEK_MODEL="test-model",
        LANGGRAPH_PG_DSN=SecretStr(""),
    )
    engine = MagicMock()
    engine.dispose = AsyncMock()
    monkeypatch.setattr(lifespan_module, "Settings", lambda: settings)
    monkeypatch.setattr(
        lifespan_module,
        "AmapMCPSettings",
        lambda: SimpleNamespace(api_key=SecretStr("test-key")),
    )
    client = object()
    monkeypatch.setattr(lifespan_module, "AmapMCPClient", lambda settings: client)
    monkeypatch.setattr(lifespan_module, "create_engine", lambda settings: engine)
    monkeypatch.setattr(lifespan_module, "async_sessionmaker", MagicMock())
    agents = {
        role: AsyncMock()
        for role in ("researcher", "context_analyst", "planner", "reviewer")
    }
    build = AsyncMock(return_value=agents)
    monkeypatch.setattr(lifespan_module, "build_agents", build)
    return engine, client, agents, build


@pytest.mark.asyncio
async def test_lifespan_caches_parent_graph_without_executing_agents(runtime_resources):
    engine, client, agents, build = runtime_resources
    app = FastAPI()
    request = SimpleNamespace(app=app)
    async with lifespan_module.lifespan(app):
        assert app.state.agents is agents
        assert get_trip_graph(request) is app.state.trip_graph
        assert "planner" in app.state.trip_graph.get_graph().nodes
        assert isinstance(app.state.trip_graph.checkpointer, InMemorySaver)
        result = await app.state.trip_graph.ainvoke(
            {}, config={"configurable": {"thread_id": "lifespan-clarify"}}
        )
        assert result["__interrupt__"][0].value["type"] == "clarify"
        build.assert_awaited_once_with(client)
        for agent in agents.values():
            agent.ainvoke.assert_not_awaited()
    assert app.state.trip_graph is None
    assert app.state.agents is None
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialization_failure_leaves_graph_unavailable(
    runtime_resources, caplog
):
    engine, _, _, build = runtime_resources
    build.side_effect = ValueError("secret-key-must-not-appear")
    app = FastAPI()
    async with lifespan_module.lifespan(app):
        assert app.state.agents is None
        with pytest.raises(HTTPException) as error:
            get_trip_graph(SimpleNamespace(app=app))
        assert error.value.status_code == 503
    assert "secret-key-must-not-appear" not in caplog.text
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_mcp_skips_agents_and_parent_graph(
    monkeypatch, runtime_resources
):
    _, _, _, build = runtime_resources
    monkeypatch.setattr(
        lifespan_module,
        "AmapMCPSettings",
        lambda: SimpleNamespace(api_key=SecretStr("")),
    )
    app = FastAPI()
    async with lifespan_module.lifespan(app):
        assert app.state.trip_graph is None
        build.assert_not_awaited()


@pytest.mark.asyncio
async def test_lifespan_binds_checkpoint_and_closes_it_on_exit(
    monkeypatch, runtime_resources
):
    engine, _, _, _ = runtime_resources
    saver = InMemorySaver()
    closed = []

    @asynccontextmanager
    async def open_saver(settings):
        try:
            yield saver
        finally:
            closed.append(True)

    monkeypatch.setattr(lifespan_module, "open_checkpointer", open_saver)
    app = FastAPI()
    with pytest.raises(RuntimeError, match="request failed"):
        async with lifespan_module.lifespan(app):
            assert app.state.trip_graph.checkpointer is saver
            assert closed == []
            raise RuntimeError("request failed")
    assert closed == [True]
    assert app.state.trip_graph is None
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_checkpoint_failure_leaves_graph_unavailable_without_leaking_secrets(
    monkeypatch, runtime_resources, caplog
):
    engine, _, _, _ = runtime_resources

    @asynccontextmanager
    async def open_saver(settings):
        raise OperationalError("password=do-not-leak")
        yield

    monkeypatch.setattr(lifespan_module, "open_checkpointer", open_saver)
    app = FastAPI()
    async with lifespan_module.lifespan(app):
        assert app.state.trip_graph is None
        with pytest.raises(HTTPException) as error:
            get_trip_graph(SimpleNamespace(app=app))
        assert error.value.status_code == 503
    assert "password=do-not-leak" not in caplog.text
    engine.dispose.assert_awaited_once()
