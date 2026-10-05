from contextlib import asynccontextmanager
from typing import TypedDict
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from psycopg.conninfo import conninfo_to_dict

from backend.app.core.config import Settings
from backend.app.graph.checkpoints import open_checkpointer
from backend.scripts import init_checkpoints


def settings_for(dsn: str = "") -> Settings:
    return Settings(
        _env_file=None,
        database_dsn="postgresql://business:unused@localhost/business",
        DEEPSEEK_API_KEY="unused",
        DEEPSEEK_BASE_URL="https://example.invalid",
        LANGGRAPH_PG_DSN=dsn,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("dsn", ["", "   "])
async def test_memory_retains_graph_state_only_within_saver(dsn, caplog):
    class State(TypedDict):
        count: int

    builder = StateGraph(State)
    builder.add_node("increment", lambda state: {"count": state["count"] + 1})
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    config = {"configurable": {"thread_id": "test-trip"}}

    with patch(
        "backend.app.graph.checkpoints.AsyncPostgresSaver.from_conn_string"
    ) as connect:
        async with open_checkpointer(settings_for(dsn)) as saver:
            assert isinstance(saver, InMemorySaver)
            graph = builder.compile(checkpointer=saver)
            await graph.ainvoke({"count": 0}, config)
            assert (await graph.aget_state(config)).values == {"count": 1}
        async with open_checkpointer(settings_for(dsn)) as new_saver:
            graph = builder.compile(checkpointer=new_saver)
            assert (await graph.aget_state(config)).values == {}
        connect.assert_not_called()
    assert "LANGGRAPH_PG_DSN 未配置" in caplog.text


@pytest.mark.asyncio
async def test_postgres_uses_checkpoint_dsn_and_closes_on_exit():
    sentinel = object()
    closed = []

    @asynccontextmanager
    async def connect(conninfo):
        params = conninfo_to_dict(conninfo)
        assert params["dbname"] == "checkpoints"
        assert params["connect_timeout"] == "5"
        try:
            yield sentinel
        finally:
            closed.append(True)

    with patch(
        "backend.app.graph.checkpoints.AsyncPostgresSaver.from_conn_string", connect
    ):
        async with open_checkpointer(
            settings_for("postgresql://checkpoint:unused@localhost/checkpoints")
        ) as saver:
            assert saver is sentinel
    assert closed == [True]


@pytest.mark.asyncio
async def test_postgres_connection_failure_is_not_hidden():
    with patch(
        "backend.app.graph.checkpoints.AsyncPostgresSaver.from_conn_string",
        side_effect=ConnectionError("database unavailable"),
    ):
        with pytest.raises(ConnectionError, match="database unavailable"):
            async with open_checkpointer(
                settings_for("postgresql://checkpoint:unused@localhost/checkpoints")
            ):
                pytest.fail("Connection failure must not fall back to memory")


@pytest.mark.asyncio
async def test_init_script_skips_memory_mode(capsys):
    with (
        patch.object(init_checkpoints, "Settings", return_value=settings_for()),
        patch.object(init_checkpoints, "open_checkpointer") as open_saver,
    ):
        await init_checkpoints.main()
        open_saver.assert_not_called()
    assert "无需初始化数据库表" in capsys.readouterr().out
