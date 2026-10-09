import asyncio

from backend.app.integrations.amap_routes import (
    AmapRouteClient,
    RouteProviderError,
    coordinates,
)
from backend.app.schemas.itinerary import SavedItineraryDetail
from backend.app.schemas.route import DayRoutes, RouteLeg, RouteMode


def transport_mode(value: str | None) -> RouteMode | None:
    # 自由文本只识别明确单一方式，混合/未知方式交给用户选择，不擅自猜测。
    modes = {
        "walking": ("walking", "步行", "徒步", "走路"),
        "driving": ("driving", "驾车", "自驾", "开车", "打车", "出租车", "网约车"),
        "bicycling": ("bicycling", "骑行", "骑车", "自行车"),
        "transit": ("transit", "公交", "地铁", "公共交通"),
    }
    matches = [
        mode
        for mode, names in modes.items()
        if any(name in (value or "").lower() for name in names)
    ]
    return matches[0] if len(matches) == 1 else None


async def get_day_routes(
    record: SavedItineraryDetail,
    day: int,
    client: AmapRouteClient,
    mode: RouteMode | None = None,
) -> DayRoutes:
    plan = next((entry for entry in record.itinerary.days if entry.day == day), None)
    if plan is None:
        raise LookupError("该行程没有指定天数。")
    places = {
        place.id: place
        for place in record.candidates.attractions
        + record.candidates.restaurants
        + record.candidates.hotels
    }

    async def leg(index: int) -> RouteLeg:
        previous, visit = plan.visits[index - 1], plan.visits[index]
        chosen = mode or transport_mode(visit.transport)
        result = RouteLeg(
            index=index,
            from_place_id=previous.place_id,
            to_place_id=visit.place_id,
            mode=chosen,
            planned_transport=visit.transport,
            planned_minutes=visit.travel_minutes,
            status="unavailable",
        )
        try:
            if chosen is None:
                raise RouteProviderError(
                    "交通方式未明确或包含多种方式，请选择一种路线方式。"
                )
            origin, destination = (
                places.get(previous.place_id),
                places.get(visit.place_id),
            )
            if origin is None or destination is None:
                raise RouteProviderError("路线所需地点信息缺失。")
            if origin.source.lower() != "amap" or destination.source.lower() != "amap":
                raise RouteProviderError("地点坐标来源暂不支持，请使用高德地点。")
            result.route, result.cached = await client.route(
                coordinates(origin.location),
                coordinates(destination.location),
                chosen,
                record.destination_city,
            )
            result.status = "ok"
        except RouteProviderError as exc:
            result.error = str(exc)
        return result

    return DayRoutes(
        itinerary_id=record.id,
        day=day,
        cache_ttl_seconds=client.settings.GD_ROUTE_CACHE_TTL_SECONDS,
        legs=list(await asyncio.gather(*(leg(i) for i in range(1, len(plan.visits))))),
    )
