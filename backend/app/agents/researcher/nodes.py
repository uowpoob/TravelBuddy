from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from backend.app.agents.researcher.state import ResearcherState
from backend.app.graph.context import TravelBuddyContext


class ResearchNode:
    """专业 Agent 的内部执行节点，暂保留接口。"""

    async def __call__(
        self,
        state: ResearcherState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        """后续调用 Agent 并返回 candidates；当前不实现执行逻辑。"""
        return {}
