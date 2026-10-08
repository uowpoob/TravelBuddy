from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.config import AuthSettings
from backend.app.core.security import (
    AuthConfigurationError,
    InvalidAccessToken,
    access_token_user_id,
    require_auth_configuration,
)
from backend.app.integrations.mcp import AmapMCPClient
from backend.app.models import User
from backend.app.repositories.users import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    async with factory() as session:
        yield session


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    try:
        settings = AuthSettings()
        require_auth_configuration(settings)
    except (ValidationError, AuthConfigurationError):
        raise HTTPException(
            status_code=503, detail="登录配置未就绪，请配置认证密钥并重启服务。"
        ) from None
    return settings


def authentication_error(detail: str = "登录凭证无效或已过期。") -> HTTPException:
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> User:
    """从签名令牌确定身份并查询用户，后续业务接口可复用该依赖。"""
    if credentials is None:
        raise authentication_error("请先登录。")
    try:
        user_id = access_token_user_id(credentials.credentials, settings)
    except InvalidAccessToken:
        raise authentication_error() from None
    try:
        user = await UserRepository(session).get_by_id(user_id)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    if user is None:
        raise authentication_error()
    return user


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
