from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from backend.app.agents.planner.state import PlannerState
from backend.app.graph.context import TravelBuddyContext


class PlanNode:
    """专业 Agent 的内部执行节点，暂保留接口。"""

    async def __call__(
        self,
        state: PlannerState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        """后续调用 Agent 并返回 itinerary；当前不实现执行逻辑。"""
        return {}
