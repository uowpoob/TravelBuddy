from langgraph.runtime import Runtime

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class ConfirmNode:
    """等待用户确认方案或提出修改要求。"""

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """后续返回更新字段：messages、confirmed。"""
        # 骨架阶段返回空更新，不修改状态。
        return {}
