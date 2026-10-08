from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.planner.state import PlannerState
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class PlannerNode:
    """调用规划子图，传入调研结果与可选的修订信息。"""

    def __init__(self, graph: CompiledStateGraph):
        self.graph = graph

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        review = state.get("review_result")
        graph_input: PlannerState = {
            "messages": [],
            "trip_request": state["trip_request"],
            "candidates": state["candidates"],
            "travel_constraints": state["travel_constraints"],
            "review_result": review,
            "itinerary": state.get("itinerary"),
        }
        result = await self.graph.ainvoke(
            graph_input, config=config, context=runtime.context
        )
        # 初次规划不计为修订；仅 Reviewer 要求 revise 时累加。
        revision_count = state.get("revision_count", 0)
        if review is not None and review.decision == "revise":
            revision_count += 1
        # 与方案一起进入 checkpoint；Confirm/Save 重试不能重新生成保存标识。
        return {
            "itinerary": result["itinerary"],
            "revision_count": revision_count,
            "save_key": str(uuid4()),
            "confirmed": False,
            "saved_itinerary_id": None,
            "saved_itinerary_version": None,
        }
