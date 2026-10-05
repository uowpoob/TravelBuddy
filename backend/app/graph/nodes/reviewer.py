from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.reviewer.state import ReviewerState
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class ReviewerNode:
    """调用审核子图，只将审核结论与澄清问题交回主图。"""

    def __init__(self, agent: CompiledStateGraph):
        self.agent = agent

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        agent_input: ReviewerState = {
            "messages": [],
            "trip_request": state["trip_request"],
            "candidates": state["candidates"],
            "travel_constraints": state["travel_constraints"],
            "itinerary": state["itinerary"],
            # 确定性的业务规则检查尚未实现。
            "rule_issues": [],
        }
        result = await self.agent.ainvoke(
            agent_input, config=config, context=runtime.context
        )
        # 内部消息留在子图，主图仅接收业务结果。
        return {
            key: result[key]
            for key in ["review_result", "clarification_question"]
            if key in result
        }
