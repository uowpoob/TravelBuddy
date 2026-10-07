from collections.abc import AsyncIterator

from fastapi import HTTPException, Request
from langgraph.graph.state import CompiledStateGraph
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


def get_agents(request: Request) -> dict[str, CompiledStateGraph]:
    """获取应用启动时创建的 Agent，依赖解析不重新加载工具或创建 Agent。"""
    agents: dict[str, CompiledStateGraph] | None = request.app.state.agents
    if agents is None:
        raise HTTPException(status_code=503, detail="Agents not initialized")
    return agents


def get_trip_graph(request: Request) -> CompiledStateGraph:
    """获取已注入缓存 Agent 的总图，不在请求中重新组装。"""
    graph: CompiledStateGraph | None = request.app.state.trip_graph
    if graph is None:
        raise HTTPException(status_code=503, detail="Trip graph not initialized")
    return graph
