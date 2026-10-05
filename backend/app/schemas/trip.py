from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TripRequest(BaseModel):
    """结构化旅行需求，未提供的信息留空。"""

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


class WeatherInfo(BaseModel):
    date: date
    description: str


class TravelConstraints(BaseModel):
    """出行约束 Agent 的调研结果。"""

    weather: list[WeatherInfo] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
