"""Redis MCP 缓存；故障时跳过缓存，不阻断高德查询。"""

import asyncio
import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from backend.app.integrations.mcp.config import AmapMCPSettings

logger = logging.getLogger(__name__)

QUERY_TOOL_NAMES = frozenset(
    {
        "maps_geo",
        "maps_regeocode",
        "maps_ip_location",
        "maps_text_search",
        "maps_around_search",
        "maps_search_detail",
        "maps_weather",
        "maps_direction_walking",
        "maps_direction_bicycling",
        "maps_direction_driving",
        "maps_direction_transit_integrated",
        "maps_distance",
    }
)


class RedisMCPCache:
    def __init__(self, settings: AmapMCPSettings) -> None:
        self._prefix = settings.cache_namespace.rstrip(":")
        self._ttl = settings.cache_ttl_seconds
        self._timeout = settings.cache_timeout_seconds
        self._redis: Redis | None = None
        url = settings.redis_url.get_secret_value().strip()
        if settings.cache_enabled and self._ttl > 0 and url:
            self._redis = Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=self._timeout,
                socket_timeout=self._timeout,
                max_connections=20,
                retry=Retry(NoBackoff(), 0),
                # 兼容现有 Windows Redis 服务（旧版服务不支持 RESP3）。
                protocol=2,
            )

    def tool_key(self, name: str, arguments: dict[str, Any]) -> str | None:
        if self._redis is None or name not in QUERY_TOOL_NAMES:
            return None
        try:
            params = json.dumps(
                arguments,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError):
            return None
        return f"{self._prefix}:amap:call:{name}:{params}"

    @property
    def tools_key(self) -> str:
        return f"{self._prefix}:amap:tools"

    async def get(self, key: str) -> str | None:
        if self._redis is None:
            return None
        try:
            async with asyncio.timeout(self._timeout):
                return await self._redis.get(key)
        except (RedisError, OSError, TimeoutError, UnicodeError) as exc:
            logger.warning(
                "Redis MCP 缓存读取失败（%s），跳过缓存。", type(exc).__name__
            )
            return None

    async def set(self, key: str, value: str) -> None:
        if self._redis is None:
            return
        try:
            async with asyncio.timeout(self._timeout):
                await self._redis.set(key, value, ex=self._ttl)
        except (RedisError, OSError, TimeoutError) as exc:
            logger.warning(
                "Redis MCP 缓存写入失败（%s），跳过缓存。", type(exc).__name__
            )

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
