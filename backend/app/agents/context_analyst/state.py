from langgraph.graph import MessagesState

from backend.app.schemas.trip import TravelConstraints, TripRequest


class ContextAnalystState(MessagesState, total=False):
    """出行约束子图：内部消息记录天气等工具查询与分析。"""

    # 输入。
    trip_request: TripRequest

    # 输出：天气、约束与建议，交回主图。
    travel_constraints: TravelConstraints
