from pydantic import BaseModel, Field


class Visit(BaseModel):
    """按列表顺序游览；交通信息表示从上一个地点到达这里。"""

    place_id: str
    stay_minutes: int = Field(ge=0)
    transport: str | None = None
    travel_minutes: int | None = Field(default=None, ge=0)


class DayPlan(BaseModel):
    day: int = Field(ge=1)
    visits: list[Visit] = Field(default_factory=list)


class EstimatedCost(BaseModel):
    """全体出行人员的预计总费用，单位为人民币元。"""

    # 未查询费用时保留未知，不能以 0 冒充预算估算。
    total: float | None = Field(default=None, ge=0)
    breakdown: dict[str, float] = Field(default_factory=dict)


class Itinerary(BaseModel):
    days: list[DayPlan]
    estimated_cost: EstimatedCost
    notes: list[str] = Field(default_factory=list)
