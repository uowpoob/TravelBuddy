from collections.abc import AsyncIterator

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.integrations.mcp import AmapMCPClient


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    async with factory() as session:
        yield session


def get_amap_mcp_client(request: Request) -> AmapMCPClient:
    client: AmapMCPClient | None = request.app.state.amap_mcp_client
    if client is None:
        raise HTTPException(status_code=503, detail="AMap MCP not configured")
    return client
