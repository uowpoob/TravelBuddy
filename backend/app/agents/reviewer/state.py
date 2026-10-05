from langgraph.graph import MessagesState

from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import TravelConstraints, TripRequest


class ReviewerState(MessagesState, total=False):
    """方案审核子图：读取方案与调研证据，输出审核意见。"""

    # 输入。
    trip_request: TripRequest
    candidates: Candidates
    travel_constraints: TravelConstraints
    itinerary: Itinerary

    # 内部工作数据：代码规则检查发现的问题，供模型审核时参考。
    rule_issues: list[str]

    # 输出：交回主图，由主图决定通过、修订或请用户取舍。
    review_result: ReviewResult
    clarification_question: str | None
