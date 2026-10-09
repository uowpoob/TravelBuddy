"""高德道路查询、结构化解析与进程内有界 TTL 缓存。"""

import asyncio
import logging
import math
from collections import OrderedDict
from datetime import UTC, datetime
from time import monotonic
from typing import Any

import httpx

from backend.app.core.config import MapSettings
from backend.app.integrations.mcp.client import _RedactAPIKey
from backend.app.schemas.route import RouteGeometry, RouteMode


class RouteProviderError(ValueError):
    """可向用户展示的错误，不含供应商密钥或请求 URL。"""


def coordinates(value: str) -> tuple[float, float]:
    try:
        parts = value.split(",")
        if len(parts) != 2 or any(not part.strip() for part in parts):
            raise ValueError
        lng, lat = (float(part) for part in parts)
        if not all(math.isfinite(v) for v in (lng, lat)):
            raise ValueError
        if not (-180 <= lng <= 180 and -90 <= lat <= 90):
            raise ValueError
        return round(lng, 6), round(lat, 6)
    except (ValueError, AttributeError):
        raise RouteProviderError("地点坐标缺失或无效。") from None


def _number(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError
    return result


def _parse_result(body: dict[str, Any], mode: RouteMode) -> RouteGeometry:
    if mode == "bicycling":
        if str(body.get("errcode")) != "0":
            raise RouteProviderError("骑行路线查询失败，请检查高德服务配置或稍后重试。")
        plans = body.get("data", {}).get("paths", [])
    else:
        if str(body.get("status")) != "1":
            raise RouteProviderError(
                "路线查询失败，请检查高德服务配置、配额或稍后重试。"
            )
        plans = body.get("route", {}).get(
            "transits" if mode == "transit" else "paths", []
        )
    if not plans:
        raise RouteProviderError("未找到可用路线。")
    plan = plans[0]
    steps = []
    if mode == "transit":
        for segment in plan.get("segments", []):
            walking = segment.get("walking")
            if isinstance(walking, dict):
                steps.extend(walking.get("steps", []))
            bus = segment.get("bus")
            lines = bus.get("buslines", []) if isinstance(bus, dict) else []
            if lines:
                steps.append(lines[0])
            railway = segment.get("railway")
            if isinstance(railway, dict) and railway.get("id"):
                raise RouteProviderError("该方案包含暂不支持绘制的铁路路段。")
    else:
        steps = plan.get("steps", [])
    paths = []
    instructions = []
    for step in steps:
        polyline = step.get("polyline")
        if isinstance(polyline, str) and polyline:
            path = [coordinates(point) for point in polyline.split(";")]
            if len(path) >= 2:
                paths.append(path)
        elif _number(step.get("distance", 0)) > 0:
            raise RouteProviderError("路线缺少道路坐标，暂时无法绘制。")
        instruction = step.get("instruction") or step.get("name")
        if isinstance(instruction, str) and instruction:
            instructions.append(instruction)
    if not paths:
        raise RouteProviderError("路线缺少道路坐标，暂时无法绘制。")
    return RouteGeometry(
        distance_meters=_number(plan["distance"]),
        duration_seconds=_number(plan["duration"]),
        paths=paths,
        instructions=instructions,
        queried_at=datetime.now(UTC),
    )


class AmapRouteClient:
    def __init__(self, settings: MapSettings):
        self.settings = settings
        self._key = settings.GD_API_KEY.get_secret_value().strip()
        for secret in (self._key, settings.GD_JSAPI_SECURITY_CODE.get_secret_value()):
            if secret:
                logging.getLogger("httpx").addFilter(_RedactAPIKey(secret))
        self.http = httpx.AsyncClient(timeout=settings.GD_ROUTE_TIMEOUT_SECONDS)
        self._cache: OrderedDict[tuple, tuple[float, RouteGeometry]] = OrderedDict()
        self._pending: dict[tuple, asyncio.Task[RouteGeometry]] = {}
        self._slots = asyncio.Semaphore(4)

    async def close(self):
        tasks = list(self._pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.http.aclose()

    async def route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        mode: RouteMode,
        city: str,
    ) -> tuple[RouteGeometry, bool]:
        if origin == destination:
            return RouteGeometry(
                distance_meters=0,
                duration_seconds=0,
                paths=[],
                queried_at=datetime.now(UTC),
            ), False
        strategy = "0"  # v3 驾车速度优先；公交最快捷；其余方式无策略参数。
        key = (origin, destination, mode, strategy, city if mode == "transit" else "")
        now = monotonic()
        for stale in [
            entry for entry, (expires, _) in self._cache.items() if expires <= now
        ]:
            self._cache.pop(stale)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key][1].model_copy(deep=True), True
        task = self._pending.get(key)
        if task is None:
            # 限制排队量，重复请求共享同一查询；断开一个请求不取消其他等待者。
            if len(self._pending) >= self.settings.GD_ROUTE_CACHE_MAX_ENTRIES:
                raise RouteProviderError("路线服务繁忙，请稍后重试。")
            task = asyncio.create_task(
                self._fetch_cached(key, origin, destination, mode, city)
            )
            self._pending[key] = task

            def done(completed: asyncio.Task):
                self._pending.pop(key, None)
                if not completed.cancelled():
                    completed.exception()

            task.add_done_callback(done)
        return (await asyncio.shield(task)).model_copy(deep=True), False

    async def _fetch_cached(
        self, key, origin, destination, mode, city
    ) -> RouteGeometry:
        if not self._key:
            raise RouteProviderError("请配置后端 GD_API_KEY 后重启服务。")
        endpoint = {
            "walking": "v3/direction/walking",
            "driving": "v3/direction/driving",
            "bicycling": "v4/direction/bicycling",
            "transit": "v3/direction/transit/integrated",
        }[mode]
        params = {
            "key": self._key,
            "origin": f"{origin[0]:.6f},{origin[1]:.6f}",
            "destination": f"{destination[0]:.6f},{destination[1]:.6f}",
            "output": "json",
        }
        if mode == "driving":
            params.update(strategy="0", extensions="all")
        elif mode == "transit":
            params.update(city=city, cityd=city, strategy="0", extensions="all")
        try:
            async with (
                asyncio.timeout(self.settings.GD_ROUTE_TIMEOUT_SECONDS * 2),
                self._slots,
            ):
                response = await self.http.get(
                    f"https://restapi.amap.com/{endpoint}", params=params
                )
                response.raise_for_status()
                result = _parse_result(response.json(), mode)
        except RouteProviderError:
            raise
        except (
            httpx.HTTPError,
            TimeoutError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            IndexError,
        ):
            raise RouteProviderError(
                "高德路线服务暂时不可用或返回数据不完整，请稍后重试。"
            ) from None
        self._cache[key] = (
            monotonic() + self.settings.GD_ROUTE_CACHE_TTL_SECONDS,
            result,
        )
        self._cache.move_to_end(key)
        while len(self._cache) > self.settings.GD_ROUTE_CACHE_MAX_ENTRIES:
            self._cache.popitem(last=False)
        return result
