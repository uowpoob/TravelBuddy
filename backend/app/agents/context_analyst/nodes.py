from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from backend.app.agents.context_analyst.state import ContextAnalystState
from backend.app.graph.context import TravelBuddyContext


class AnalyzeContextNode:
    """专业 Agent 的内部执行节点，暂保留接口。"""

    async def __call__(
        self,
        state: ContextAnalystState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        """后续调用 Agent 并返回 travel_constraints；当前不实现执行逻辑。"""
        return {}
