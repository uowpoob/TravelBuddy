from langgraph.runtime import Runtime

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class SaveNode:
    """保存用户确认后的行程。"""

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """后续返回更新字段：saved_itinerary_id。"""
        # 骨架阶段返回空更新，不修改状态。
        return {}
