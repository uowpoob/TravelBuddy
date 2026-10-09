from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import TravelConstraints, TripRequest


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
    """Planner 的结构化输出，同时保存在 TripState.itinerary。"""

    days: list[DayPlan]
    estimated_cost: EstimatedCost
    notes: list[str] = Field(default_factory=list)


class SavedItineraryPublic(BaseModel):
    """已保存行程的列表摘要，每个确认版本独立展示。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    version: int
    title: str
    destination_city: str
    start_date: date
    days: int
    created_at: datetime


class SavedItineraryDetail(SavedItineraryPublic):
    """完整版本快照，不依赖会话 checkpoint。"""

    trip_request: TripRequest
    itinerary: Itinerary
    candidates: Candidates
    travel_constraints: TravelConstraints | None
    review_result: ReviewResult | None
