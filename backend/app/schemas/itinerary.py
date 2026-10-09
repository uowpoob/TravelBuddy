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
    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="已确认的部分费用，项目名称使用面向旅行者的中文，如交通、门票；金额为全体人员的人民币费用。",
    )


class Itinerary(BaseModel):
    """Planner 的结构化输出，同时保存在 TripState.itinerary。"""

    days: list[DayPlan]
    estimated_cost: EstimatedCost
    notes: list[str] = Field(
        default_factory=list,
        description="直接展示给旅行者的简短行程提醒，说明实际影响与建议；不含 Agent、工具、字段名、null/非 0 说明或推理审核过程。",
    )


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
