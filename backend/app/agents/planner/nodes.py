import json

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.planner.state import PlannerState
from backend.app.graph.context import TravelBuddyContext
from backend.app.schemas.itinerary import Itinerary


class PlanNode:
    """调用已构建的规划 Agent，支持携带旧行程和审核意见。"""

    def __init__(self, agent: CompiledStateGraph):
        self.agent = agent

    async def __call__(
        self,
        state: PlannerState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        review = state.get("review_result")
        itinerary = state.get("itinerary")
        payload = {
            "trip_request": state["trip_request"].model_dump(mode="json"),
            "candidates": state["candidates"].model_dump(mode="json"),
            "travel_constraints": state["travel_constraints"].model_dump(mode="json"),
            "review_result": review.model_dump(mode="json") if review else None,
            "itinerary": itinerary.model_dump(mode="json") if itinerary else None,
        }
        message = HumanMessage(content=json.dumps(payload, ensure_ascii=False))
        result = await self.agent.ainvoke(
            {"messages": [message]}, config=config, context=runtime.context
        )
        return {
            "messages": result["messages"],
            "itinerary": Itinerary.model_validate(result["structured_response"]),
        }
