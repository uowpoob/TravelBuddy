"""通过官方 MCP Python SDK 连接高德的 Streamable HTTP 服务。"""

import logging
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Any, Self
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, PaginatedRequestParams, Tool
from pydantic import SecretStr, TypeAdapter, ValidationError

from backend.app.integrations.mcp.cache import RedisMCPCache
from backend.app.integrations.mcp.config import AmapMCPSettings

logger = logging.getLogger(__name__)
_TOOL_LIST_ADAPTER = TypeAdapter(list[Tool])


class AmapMCPError(RuntimeError):
    """不包含连接密钥的 MCP 连接或协议错误。"""


class AmapMCPConfigurationError(AmapMCPError):
    """高德 MCP 缺少必要配置。"""


class _RedactAPIKey(logging.Filter):
    """高德通过 URL 鉴权，SDK 的 HTTP 日志需要隐藏其中的密钥。"""

    def __init__(self, api_key: str) -> None:
        super().__init__()
        self._secrets = (api_key, quote_plus(api_key))

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "[REDACTED]")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_text = self._redact(
                "".join(traceback.format_exception(*record.exc_info))
            )
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = self._redact(record.exc_text)
        return True


class AmapMCPClient:
    """复用 Redis 缓存；未命中时创建并关闭独立 MCP 会话。

    构造时不访问网络。会话在调用它的同一个任务内打开和关闭，
    避免 FastAPI 请求之间跨任务退出 SDK 的异步上下文。
    """

    def __init__(self, settings: AmapMCPSettings | None = None) -> None:
        settings = settings if settings is not None else AmapMCPSettings()
        api_key = settings.api_key.get_secret_value().strip()
        if not api_key:
            raise AmapMCPConfigurationError(
                "请在项目 .env 中设置 GD_API_KEY（高德 Web 服务 Key）。"
            )

        parts = urlsplit(str(settings.server_url))
        query = [(key, value) for key, value in parse_qsl(parts.query) if key != "key"]
        query.append(("key", api_key))
        self._url = SecretStr(
            urlunsplit(parts._replace(query=urlencode(query), fragment=""))
        )
        self._timeout_seconds = settings.timeout_seconds
        self._cache = RedisMCPCache(settings)

        redactor = _RedactAPIKey(api_key)
        for name in ("mcp.client.streamable_http", "client", "httpx", "httpx2"):
            logging.getLogger(name).addFilter(redactor)

    async def close(self) -> None:
        """关闭本客户端持有的 Redis 连接池。"""
        await self._cache.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        try:
            async with (
                streamable_http_client(self._url.get_secret_value()) as (
                    read_stream,
                    write_stream,
                ),
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=self._timeout_seconds,
                ) as session,
            ):
                await session.initialize()
                yield session
        except AmapMCPError:
            raise
        except Exception:  # noqa: BLE001 -- sanitize all SDK errors containing auth URLs
            # SDK/HTTP 异常可能包含鉴权 URL，不向调用方暴露原始异常链。
            raise AmapMCPError(
                "高德 MCP 连接或请求失败，请检查 GD_API_KEY、"
                "GD_MCP_URL、网络及请求超时配置。"
            ) from None

    @staticmethod
    async def _list_tools(session: ClientSession) -> list[Tool]:
        tools: list[Tool] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            params = (
                PaginatedRequestParams(cursor=cursor) if cursor is not None else None
            )
            page = await session.list_tools(params=params)
            tools.extend(page.tools)
            cursor = page.next_cursor
            if cursor is None:
                return tools
            if cursor in seen_cursors:
                raise AmapMCPError("高德 MCP 工具列表返回了重复的分页游标。")
            seen_cursors.add(cursor)

    async def list_tools(self) -> list[Tool]:
        """发现所有工具，保留名称、描述及原始输入输出 schema。"""
        key = self._cache.tools_key
        cached = await self._cache.get(key)
        if cached is not None:
            try:
                return _TOOL_LIST_ADAPTER.validate_json(cached)
            except ValidationError:
                logger.warning("Redis MCP 工具列表缓存无效，重新发现工具。")
        async with self._session() as session:
            tools = await self._list_tools(session)
        await self._cache.set(
            key, _TOOL_LIST_ADAPTER.dump_json(tools, by_alias=True).decode("utf-8")
        )
        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> CallToolResult:
        """调用已发现的工具；保留 content、structuredContent 与 isError。

        is_error=True 是服务端返回的工具执行失败，调用方应显式处理。
        连接、协议或未知工具错误则抛出 AmapMCPError。
        查询工具的成功结果缓存一小时；参数不同的查询使用不同缓存键。
        """
        if not name.strip():
            raise ValueError("工具名称不能为空。")
        # 在第一次异步等待前固定参数，保证缓存键与实际请求一致。
        params = deepcopy(arguments or {})
        key = self._cache.tool_key(name, params)
        if key is not None:
            cached = await self._cache.get(key)
            if cached is not None:
                try:
                    result = CallToolResult.model_validate_json(cached)
                    if not result.is_error:
                        return result
                except ValidationError:
                    logger.warning("Redis MCP 查询缓存无效，重新查询高德。")
        async with self._session() as session:
            result = await session.call_tool(name, arguments=params)
        if key is not None and not result.is_error:
            await self._cache.set(key, result.model_dump_json(by_alias=True))
        return result
