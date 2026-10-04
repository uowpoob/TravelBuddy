import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from backend.app.core.config import Settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def open_checkpointer(settings: Settings) -> AsyncIterator[BaseCheckpointSaver]:
    """Use memory unless a checkpoint DSN is configured; initialize PG separately."""
    dsn = settings.LANGGRAPH_PG_DSN.get_secret_value().strip()
    if not dsn:
        logger.warning(
            "LANGGRAPH_PG_DSN 未配置，检查点仅保存在内存中，进程重启后丢失。"
        )
        yield InMemorySaver()
        return

    conninfo = make_conninfo(
        dsn, connect_timeout=5
    )
    async with AsyncPostgresSaver.from_conn_string(conninfo) as saver:
        yield saver
