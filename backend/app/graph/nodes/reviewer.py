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
    ) -> dict[str, object]:
        agent_input: ReviewerState = {
            "messages": [],
            "trip_request": state["trip_request"],
            "candidates": state["candidates"],
            "travel_constraints": state["travel_constraints"],
            "itinerary": state["itinerary"],
            "rule_issues": [],
        }
        result = await self.agent.ainvoke(agent_input, context=runtime.context)
        # 只提取业务输出；占位节点尚未生成的字段不返回，内部 messages 不回传。
        return {
            key: result[key]
            for key in ["review_result", "clarification_question"]
            if key in result
        }
