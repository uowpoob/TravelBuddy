from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.config import Settings
from backend.app.db.session import create_engine
from backend.app.integrations.mcp import AmapMCPClient, AmapMCPSettings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_engine = None
    app.state.session_factory = None
    app.state.amap_mcp_client = None
    mcp_settings = AmapMCPSettings()
    if mcp_settings.api_key.get_secret_value().strip():
        # 仅保存客户端配置，实际请求时再连接高德，不影响离线启动。
        app.state.amap_mcp_client = AmapMCPClient(mcp_settings)
    try:
        settings = Settings()
    except ValidationError:
        pass
    else:
        app.state.db_engine = create_engine(settings)
        app.state.session_factory = async_sessionmaker(
            app.state.db_engine, expire_on_commit=False
        )
    try:
        yield
    finally:
        if app.state.db_engine is not None:
            await app.state.db_engine.dispose()
