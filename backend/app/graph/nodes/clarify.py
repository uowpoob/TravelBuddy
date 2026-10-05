from langgraph.runtime import Runtime

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class ClarifyNode:
    """等待用户补充信息或对冲突条件作出选择。"""

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """后续返回更新字段：messages。"""
        # 骨架阶段返回空更新，不修改状态。
        return {}
