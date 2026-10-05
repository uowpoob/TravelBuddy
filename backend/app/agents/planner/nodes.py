from langgraph.runtime import Runtime

from backend.app.agents.planner.state import PlannerState
from backend.app.graph.context import TravelBuddyContext


class PlanNode:
    """行程规划 Agent 的内部执行节点。"""

    async def __call__(
        self,
        state: PlannerState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """后续返回：itinerary。模型与工具逻辑暂不实现。"""
        return {}
