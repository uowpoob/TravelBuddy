import json

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.reviewer.state import ReviewerState
from backend.app.graph.context import TravelBuddyContext
from backend.app.schemas.review import ReviewResult


class ReviewNode:
    """调用已构建的审核 Agent，将结论和澄清问题写入子图。"""

    def __init__(self, agent: CompiledStateGraph):
        self.agent = agent

    async def __call__(
        self,
        state: ReviewerState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        payload = {
            "trip_request": state["trip_request"].model_dump(mode="json"),
            "days": [
                day.model_dump(mode="json")
                for day in state["itinerary"].days
            ],
            "places": {
                place.id: place.name
                for place in state["candidates"].attractions
                + state["candidates"].restaurants
                + state["candidates"].hotels
            },
            "rule_issues": state.get("rule_issues", []),
            "revision_request": state.get("revision_request"),
            "revision_count": state.get("revision_count", 0),
            "previous_review": (
                state["previous_review"].model_dump(mode="json")
                if state.get("previous_review") is not None
                else None
            ),
        }
        message = HumanMessage(content=json.dumps(payload, ensure_ascii=False))
        result = await self.agent.ainvoke(
            {"messages": [message]}, config=config, context=runtime.context
        )
        review = ReviewResult.model_validate(result["structured_response"])
        return {
            "messages": result["messages"],
            "review_result": review,
            "clarification_question": review.clarification_question,
        }
