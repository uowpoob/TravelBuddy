import asyncio
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from mcp.types import CallToolResult, Tool
from pydantic import SecretStr
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from backend.app.integrations.mcp import AmapMCPClient, AmapMCPSettings


def make_client(**options):
    return AmapMCPClient(
        AmapMCPSettings(
            _env_file=None,
            api_key=SecretStr("test-key"),
            redis_url=SecretStr(options.pop("redis_url", "redis://127.0.0.1:6379/0")),
            cache_enabled=True,
            cache_ttl_seconds=3600,
            cache_namespace=f"travelbuddy:test:{uuid4()}",
            **options,
        )
    )


def mock_session(monkeypatch, client, result):
    session = SimpleNamespace(
        call_tool=AsyncMock(return_value=result),
        list_tools=AsyncMock(
            return_value=SimpleNamespace(
                tools=[Tool(name="maps_weather", inputSchema={"type": "object"})],
                next_cursor=None,
            )
        ),
    )

    @asynccontextmanager
    async def open_session():
        yield session

    monkeypatch.setattr(client, "_session", open_session)
    return session


@pytest.mark.asyncio
async def test_plain_keys_normalize_parameters_and_exclude_unlisted_tools():
    async with make_client() as client:
        cache = client._cache
        key = cache.tool_key("maps_text_search", {"city": "杭州", "keywords": "景点"})
        assert key == cache.tool_key(
            "maps_text_search", {"keywords": "景点", "city": "杭州"}
        )
        assert key.endswith(':maps_text_search:{"city":"杭州","keywords":"景点"}')
        assert key != cache.tool_key("maps_text_search", {"keywords": "公园"})
        assert cache.tool_key("unknown_write_tool", {}) is None


@pytest.mark.asyncio
async def test_redis_outage_does_not_block_mcp(monkeypatch):
    async with make_client() as client:
        result = CallToolResult(content=[])
        session = mock_session(monkeypatch, client, result)
        monkeypatch.setattr(
            client._cache._redis, "get", AsyncMock(side_effect=ConnectionError())
        )
        monkeypatch.setattr(
            client._cache._redis, "set", AsyncMock(side_effect=ConnectionError())
        )
        assert await client.call_tool("maps_weather", {"city": "杭州"}) is result
        session.call_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_tool_error_not_cached(monkeypatch):
    async with make_client() as client:
        result = CallToolResult(content=[], isError=True)
        mock_session(monkeypatch, client, result)
        monkeypatch.setattr(client._cache, "get", AsyncMock(return_value=None))
        writer = AsyncMock()
        monkeypatch.setattr(client._cache, "set", writer)
        assert (await client.call_tool("maps_weather")).is_error
        writer.assert_not_awaited()


@pytest.mark.asyncio
async def test_corrupt_cache_is_refreshed(monkeypatch):
    async with make_client() as client:
        result = CallToolResult(content=[])
        session = mock_session(monkeypatch, client, result)
        monkeypatch.setattr(
            client._cache, "get", AsyncMock(return_value="invalid-json")
        )
        writer = AsyncMock()
        monkeypatch.setattr(client._cache, "set", writer)
        assert await client.call_tool("maps_weather") is result
        session.call_tool.assert_awaited_once()
        writer.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("TRAVELBUDDY_TEST_REDIS_URL"), reason="Redis smoke test opt-in"
)
async def test_real_redis_shared_results_discovery_and_one_hour_ttl(monkeypatch):
    url = os.environ["TRAVELBUDDY_TEST_REDIS_URL"]
    namespace = f"travelbuddy:test:{uuid4()}"
    result = CallToolResult.model_validate(
        {
            "content": [{"type": "text", "text": "景点"}],
            "structuredContent": {"ids": [1]},
        }
    )
    keys = []
    async with (
        Redis.from_url(url, protocol=2) as redis,
        make_client(redis_url=url) as first,
        make_client(redis_url=url) as second,
    ):
        first._cache._prefix = second._cache._prefix = namespace
        first_session = mock_session(monkeypatch, first, result)
        second_session = mock_session(monkeypatch, second, result)
        args = {"city": "杭州", "keywords": "景点"}
        key = first._cache.tool_key("maps_text_search", args)
        extra_key = first._cache.tool_key(
            "maps_text_search", {**args, "keywords": "公园"}
        )
        keys = [key, extra_key, first._cache.tools_key]
        try:
            assert await redis.ping()
            original = await first.call_tool("maps_text_search", args)
            original.content[0].text = "changed"
            cached = await second.call_tool(
                "maps_text_search", {"keywords": "景点", "city": "杭州"}
            )
            assert cached.content[0].text == "景点"
            assert cached.structured_content == {"ids": [1]}
            first_session.call_tool.assert_awaited_once()
            second_session.call_tool.assert_not_awaited()
            assert 3590 <= await redis.ttl(key) <= 3600
            await second.call_tool("maps_text_search", {**args, "keywords": "公园"})
            second_session.call_tool.assert_awaited_once()
            tools = await first.list_tools()
            assert await second.list_tools() == tools
            second_session.list_tools.assert_not_awaited()
            assert 3590 <= await redis.ttl(first._cache.tools_key) <= 3600
            await redis.pexpire(key, 1)
            await asyncio.sleep(0.02)
            await second.call_tool("maps_text_search", args)
            assert second_session.call_tool.await_count == 2
        finally:
            await redis.delete(*keys)
