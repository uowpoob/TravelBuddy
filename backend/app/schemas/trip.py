from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REQUIRED_FIELDS = {
    "destination_city": "目的地城市",
    "start_date": "出行日期",
    "days": "旅行天数（1–5 天）",
    "travelers": "出行人数",
    "transport": "交通方式或允许的交通方式",
}


class TripRequest(BaseModel):
    """共享业务需求，保存在 TripState.trip_request；也是 Understand 输出的内部数据。

    未提供的信息留空。
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    destination_city: str | None = None
    departure_city: str | None = None
    days: int | None = Field(default=None, ge=1, le=5)
    start_date: date | None = None
    travelers: int | None = Field(default=None, ge=1)
    budget: float | None = Field(default=None, gt=0)
    budget_scope: Literal["total", "per_person"] | None = None
    preferences: list[str] = Field(default_factory=list)
    must_visit: list[str] = Field(default_factory=list)
    transport: str | None = None
    additional_requirements: list[str] = Field(
        default_factory=list,
        description="本次旅行的其他明确要求，例如第二天下午改为室内活动。",
    )


class WeatherInfo(BaseModel):
    date: date
    description: str


def missing_request_fields(request: TripRequest) -> list[str]:
    """Understand 与保存服务共用的完整需求检查。"""
    missing = [field for field in REQUIRED_FIELDS if not getattr(request, field)]
    if request.budget is not None and request.budget_scope is None:
        missing.append("budget_scope")
    return missing


class TravelConstraints(BaseModel):
    """Context Analyst 的结构化输出，同时保存在 TripState.travel_constraints。"""

    weather: list[WeatherInfo] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
