from langgraph.runtime import Runtime

from backend.app.agents.researcher.state import ResearcherState
from backend.app.graph.context import TravelBuddyContext


class ResearchNode:
    """地点调研 Agent 的内部执行节点。"""

    async def __call__(
        self,
        state: ResearcherState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """后续返回：candidates。模型与工具逻辑暂不实现。"""
        return {}
