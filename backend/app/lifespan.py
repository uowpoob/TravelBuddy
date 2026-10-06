import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.agents.builder import build_agents
from backend.app.core.config import Settings
from backend.app.db.session import create_engine
from backend.app.integrations.mcp import AmapMCPClient, AmapMCPError, AmapMCPSettings


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_engine = None
    app.state.session_factory = None
    app.state.amap_mcp_client = None
    app.state.agents = None
    settings: Settings | None = None
    try:
        try:
            mcp_settings = AmapMCPSettings()
        except ValidationError:
            logger.warning("高德 MCP 配置无效，无法初始化 MCP 客户端。")
        else:
            if mcp_settings.api_key.get_secret_value().strip():
                app.state.amap_mcp_client = AmapMCPClient(mcp_settings)

        try:
            settings = Settings()
        except ValidationError:
            logger.warning("应用配置不完整，跳过数据库和 Agent 初始化。")
        else:
            app.state.db_engine = create_engine(settings)
            app.state.session_factory = async_sessionmaker(
                app.state.db_engine, expire_on_commit=False
            )

        if app.state.amap_mcp_client is None:
            logger.warning("高德 MCP 未配置，Agent 尚未初始化。")
        elif settings is None or not all(
            value.strip()
            for value in (
                settings.DEEPSEEK_API_KEY,
                settings.DEEPSEEK_BASE_URL,
                settings.DEEPSEEK_MODEL,
            )
        ):
            logger.warning("DeepSeek 配置不完整，Agent 尚未初始化。")
        else:
            try:
                # 每次应用启动统一发现一次工具，然后创建并复用四个 Agent。
                app.state.agents = await build_agents(app.state.amap_mcp_client)
            except (AmapMCPError, ValueError) as exc:
                # 配置异常可能包含密钥，只记录错误类型，不输出原始异常。
                logger.error(
                    "Agent 初始化失败（%s），请检查高德 MCP 和模型配置。",
                    type(exc).__name__,
                )
            else:
                logger.info("已初始化 %d 个 Agent。", len(app.state.agents))

        yield
    finally:
        app.state.agents = None
        app.state.amap_mcp_client = None
        app.state.session_factory = None
        if app.state.db_engine is not None:
            await app.state.db_engine.dispose()
