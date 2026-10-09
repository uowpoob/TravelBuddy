"""模型结构化输出的统一入口。

RequestUnderstanding 是 Understand 专用的模型输出，节点处理后更新业务状态。
其余四个输出直接复用业务对象：既约束模型输出，也作为总图 State 字段的类型。
这里导出原来的类，保持同一份字段定义、校验规则和类型身份。
"""

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import TravelConstraints, TripRequest

__all__ = [
    "Candidates",
    "Itinerary",
    "RequestUnderstanding",
    "ReviewResult",
    "TravelConstraints",
]


TripRequestField = Literal[
    "destination_city",
    "departure_city",
    "days",
    "start_date",
    "travelers",
    "budget",
    "budget_scope",
    "preferences",
    "must_visit",
    "transport",
    "additional_requirements",
]


class RequestUnderstanding(BaseModel):
    """Understand 的结构化输出；用于合并需求，不直接存入总图 State。"""

    new_trip: bool = Field(description="用户是否明确要求开始一段新的旅行。")
    updated_fields: list[TripRequestField] = Field(
        description="本轮用户明确新增、修改或清除的字段；未提及的字段不列出。"
    )
    trip_request: TripRequest
    clarification_question: str | None = Field(
        default=None, description="存在歧义或冲突时询问用户；没有时为 null。"
    )
    refresh_candidates: bool = Field(
        default=False,
        description="修改需要查询旧候选之外的新地点，或用户明确要求重新查地点时为 true。",
    )
    refresh_weather: bool = Field(
        default=False, description="用户明确要求重新查询天气时为 true。"
    )
