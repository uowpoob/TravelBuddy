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
        source = state.get("itinerary_request")
        if (
            itinerary is not None
            and source is not None
            and any(
                getattr(source, field) != getattr(state["trip_request"], field)
                for field in ("destination_city", "start_date", "transport")
            )
        ):
            # 保留旧地点顺序作为修改依据，但不沿用其他日期/交通方式下的耗时。
            itinerary = itinerary.model_copy(deep=True)
            for day in itinerary.days:
                for visit in day.visits:
                    visit.transport = None
                    visit.travel_minutes = None
        payload = {
            "trip_request": state["trip_request"].model_dump(mode="json"),
            "candidates": state["candidates"].model_dump(mode="json"),
            "travel_constraints": state["travel_constraints"].model_dump(mode="json"),
            "review_result": review.model_dump(mode="json") if review else None,
            "itinerary": itinerary.model_dump(mode="json") if itinerary else None,
        }
        if "revision_request" in state:
            payload["revision_request"] = state.get("revision_request")
            payload["changed_fields"] = state.get("changed_fields", [])
            payload["previous_trip_request"] = (
                source.model_dump(mode="json") if source else None
            )
        if runtime.context.interest_description:
            payload["user_interests"] = runtime.context.interest_description
        message = HumanMessage(content=json.dumps(payload, ensure_ascii=False))
        result = await self.agent.ainvoke(
            {"messages": [message]},
            config=config,
            context=runtime.context,
        )
        structured = result["structured_response"]
        if structured is None:
            raise RuntimeError("模型输出错误")
        return {
            "messages": result["messages"],
            "itinerary": Itinerary.model_validate(structured),
        }
