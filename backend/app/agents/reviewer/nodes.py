from langgraph.runtime import Runtime

from backend.app.agents.reviewer.state import ReviewerState
from backend.app.graph.context import TravelBuddyContext


class ReviewNode:
    """方案审核 Agent 的内部执行节点。"""

    async def __call__(
        self,
        state: ReviewerState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """后续返回：review_result、clarification_question。模型与工具逻辑暂不实现。"""
        return {}
