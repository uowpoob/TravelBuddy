from langgraph.runtime import Runtime

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class UnderstandNode:
    """理解或更新旅行需求。"""

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """后续返回更新字段：trip_request、missing_fields、clarification_question。"""
        # 骨架阶段返回空更新，不修改状态。
        return {}


