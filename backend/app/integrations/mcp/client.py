"""通过官方 MCP Python SDK 连接高德的 Streamable HTTP 服务。"""

import logging
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, PaginatedRequestParams, Tool
from pydantic import SecretStr

from backend.app.integrations.mcp.config import AmapMCPSettings


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
    """可复用的客户端配置；每次操作创建并关闭独立会话。

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

        redactor = _RedactAPIKey(api_key)
        for name in ("mcp.client.streamable_http", "client", "httpx", "httpx2"):
            logging.getLogger(name).addFilter(redactor)

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        try:
            async with streamable_http_client(self._url.get_secret_value()) as (
                read_stream,
                write_stream,
            ):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=self._timeout_seconds,
                ) as session:
                    await session.initialize()
                    yield session
        except AmapMCPError:
            raise
        except Exception:
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
        async with self._session() as session:
            return await self._list_tools(session)

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> CallToolResult:
        """调用已发现的工具；保留 content、structuredContent 与 isError。

        is_error=True 是服务端返回的工具执行失败，调用方应显式处理。
        连接、协议或未知工具错误则抛出 AmapMCPError。
        """
        if not name.strip():
            raise ValueError("工具名称不能为空。")
        async with self._session() as session:
            tools = await self._list_tools(session)
            if not any(tool.name == name for tool in tools):
                raise AmapMCPError(f"高德 MCP 未提供工具：{name}")
            return await session.call_tool(name, arguments=arguments or {})
