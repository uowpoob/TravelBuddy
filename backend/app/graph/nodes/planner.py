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
    ) -> dict[str, object]:
        agent_input: PlannerState = {
            "messages": [],
            "trip_request": state["trip_request"],
            "candidates": state["candidates"],
            "travel_constraints": state["travel_constraints"],
            "review_result": state.get("review_result"),
            "itinerary": state.get("itinerary"),
        }
        result = await self.agent.ainvoke(agent_input, context=runtime.context)
        # 只提取业务输出；占位节点尚未生成的字段不返回，内部 messages 不回传。
        return {key: result[key] for key in ["itinerary"] if key in result}
