from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.planner.state import PlannerState
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class PlannerNode:
    """调用规划子图，传入调研结果与可选的修订信息。"""

    def __init__(self, agent: CompiledStateGraph):
        self.agent = agent

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        review = state.get("review_result")
        agent_input: PlannerState = {
            "messages": [],
            "trip_request": state["trip_request"],
            "candidates": state["candidates"],
            "travel_constraints": state["travel_constraints"],
            "review_result": review,
            "itinerary": state.get("itinerary"),
        }
        result = await self.agent.ainvoke(
            agent_input, config=config, context=runtime.context
        )
        # 内部消息留在子图；修订计数逻辑后续实现。
        return {"itinerary": result["itinerary"]}
