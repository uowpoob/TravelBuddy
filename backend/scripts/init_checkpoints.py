"""Run explicitly once to initialize LangGraph checkpoint tables."""

import asyncio

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.app.core.config import Settings
from backend.app.core.runtime import loop_factory
from backend.app.graph.checkpoints import open_checkpointer


async def main():
    settings = Settings()
    if not settings.LANGGRAPH_PG_DSN.get_secret_value().strip():
        print("LANGGRAPH_PG_DSN 未配置，使用内存检查点，无需初始化数据库表。")
        return
    async with open_checkpointer(settings) as saver:
        if not isinstance(saver, AsyncPostgresSaver):
            raise TypeError("Expected a PostgreSQL checkpointer for initialization.")
        await saver.setup()
    print("LangGraph PostgreSQL checkpoint tables initialized.")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=loop_factory)
