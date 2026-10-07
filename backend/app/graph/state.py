from langgraph.graph import MessagesState

from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import TravelConstraints, TripRequest


class TripState(MessagesState, total=False):
    """主图共享状态；messages 及其合并规则继承自 MessagesState。

    total=False 允许节点逐步补充字段，不会自动为字段设置默认值。
    Understand 初始化或重置 revision_count=0、confirmed=False。
    Confirm 根据用户对当前方案的回答更新 confirmed。
    Agent 的内部 messages 留在各自子图，主图只接收其业务结果。
    """

    trip_request: TripRequest
    missing_fields: list[str]
    clarification_question: str | None
    last_understood_message_id: str | None

    # 两个并行 Agent 各自写入一个字段，Planner 汇合后读取。
    candidates: Candidates
    travel_constraints: TravelConstraints

    itinerary: Itinerary | None
    review_result: ReviewResult | None
    revision_count: int
    confirmed: bool
    saved_itinerary_id: int | None
