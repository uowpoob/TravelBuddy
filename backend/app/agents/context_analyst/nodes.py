from langgraph.runtime import Runtime

from backend.app.agents.context_analyst.state import ContextAnalystState
from backend.app.graph.context import TravelBuddyContext


class AnalyzeContextNode:
    """出行约束 Agent 的内部执行节点。"""

    async def __call__(
        self,
        state: ContextAnalystState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """后续返回：travel_constraints。模型与工具逻辑暂不实现。"""
        return {}
