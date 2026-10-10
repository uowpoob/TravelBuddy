from unittest.mock import AsyncMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.clarify import ClarifyNode
from backend.app.graph.nodes.planner import PlannerNode
from backend.app.graph.routes import route_after_review
from backend.app.graph.state import TripState
from backend.app.schemas.review import ReviewResult


@pytest.mark.asyncio
async def test_repeated_reviewer_rejection_stops_after_two_repairs(
    confirmed_trip_state,
):
    planner = AsyncMock()
    planner.ainvoke.return_value = {"itinerary": confirmed_trip_state["itinerary"]}
    builder = StateGraph(TripState, context_schema=TravelBuddyContext)
    builder.add_node("planner", PlannerNode(planner))
    builder.add_node(
        "review",
        lambda state: {
            "review_result": ReviewResult(
                decision="revise", issues=["测试不可满足约束"]
            )
        },
    )
    builder.add_node("clarify", ClarifyNode())
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "review")
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {"planner": "planner", "clarify": "clarify", "confirm": END},
    )
    builder.add_edge("clarify", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    result = await graph.ainvoke(
        {**confirmed_trip_state, "review_result": None, "revision_count": 0},
        config={"configurable": {"thread_id": "revision-limit"}},
        context=TravelBuddyContext(user_id=1, conversation_id="revision-limit"),
    )
    assert result["revision_count"] == 2
    assert result["__interrupt__"][0].value["type"] == "clarify"
    assert "测试不可满足约束" in result["__interrupt__"][0].value["question"]
    assert planner.ainvoke.await_count == 3  # initial plan plus two repairs
