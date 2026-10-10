from langgraph.graph import MessagesState

from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import TripRequest


class ReviewerState(MessagesState, total=False):
    """宽松审核子图：读取需求、活动和地点，判断通过、修订或用户取舍。"""

    # 输入。
    trip_request: TripRequest
    candidates: Candidates
    itinerary: Itinerary

    # 内部工作数据：代码规则检查发现的问题，供模型审核时参考。
    rule_issues: list[str]
    revision_request: str | None
    revision_count: int
    previous_review: ReviewResult | None

    # 输出：保留实际审核结论，由主图路由至确认、修订或澄清。
    review_result: ReviewResult
    clarification_question: str | None
