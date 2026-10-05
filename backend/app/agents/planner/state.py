from langgraph.graph import MessagesState

from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import TravelConstraints, TripRequest


class PlannerState(MessagesState, total=False):
    """行程规划子图：内部消息记录规划过程及路线、预算工具调用。"""

    # 输入：需求与两支调研结果。
    trip_request: TripRequest
    candidates: Candidates
    travel_constraints: TravelConstraints

    # 修订时输入审核意见；首次规划为空。
    review_result: ReviewResult | None

    # 修订时读取旧行程，完成后写入新行程并交回主图。
    itinerary: Itinerary | None
