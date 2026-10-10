from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.reviewer.state import ReviewerState
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState
from backend.app.schemas.review import ReviewResult
from backend.app.services.itinerary_rules import (
    check_itinerary_rules,
    enforce_rule_review,
)


class ReviewerNode:
    """基础规则供审核参考；保留通过、修订和用户取舍三种实际结论。"""

    def __init__(self, graph: CompiledStateGraph):
        self.graph = graph

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        checks = check_itinerary_rules(
            state["trip_request"], state.get("itinerary"), state["candidates"]
        )
        if state.get("itinerary") is None:
            review = ReviewResult(
                decision="revise",
                issues=checks.issues,
            )
            return {"review_result": review, "clarification_question": None}
        graph_input: ReviewerState = {
            "messages": [],
            "trip_request": state["trip_request"],
            "candidates": state["candidates"],
            "itinerary": state["itinerary"],
            "rule_issues": checks.issues,
            "revision_request": state.get("revision_request"),
            "revision_count": state.get("revision_count", 0),
            "previous_review": state.get("review_result"),
        }
        result = await self.graph.ainvoke(
            graph_input, config=config, context=runtime.context
        )
        # 只阻止基础错误被放行，不覆盖模型的 revise / needs_user，也不按次数强制 pass。
        review = enforce_rule_review(
            ReviewResult.model_validate(result["review_result"]), checks
        )
        return {
            "review_result": review,
            "clarification_question": review.clarification_question,
        }
