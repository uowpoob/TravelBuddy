from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RouteMode = Literal["walking", "driving", "bicycling", "transit"]


class RouteGeometry(BaseModel):
    distance_meters: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    # 每段 polyline 独立绘制，避免跨缺失道路或公交换乘段画出虚构连接。
    paths: list[list[tuple[float, float]]]
    instructions: list[str] = Field(default_factory=list)
    queried_at: datetime


class RouteLeg(BaseModel):
    index: int
    from_place_id: str
    to_place_id: str
    mode: RouteMode | None = None
    planned_transport: str | None = None
    planned_minutes: int | None = None
    status: Literal["ok", "unavailable"]
    error: str | None = None
    cached: bool = False
    route: RouteGeometry | None = None


class DayRoutes(BaseModel):
    itinerary_id: int
    day: int
    source: str = "amap"
    cache_ttl_seconds: int
    legs: list[RouteLeg]
