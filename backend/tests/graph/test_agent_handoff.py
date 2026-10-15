import json
from datetime import date
from unittest.mock import AsyncMock

import pytest
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from pydantic import PrivateAttr, ValidationError

from backend.app.agents.context_analyst.nodes import AnalyzeContextNode
from backend.app.agents.planner.nodes import PlanNode
from backend.app.agents.researcher.nodes import ResearchNode
from backend.app.agents.reviewer.graph import build_reviewer_graph
from backend.app.agents.reviewer.nodes import ReviewNode
from backend.app.graph.builder import build_trip_graph
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.reviewer import ReviewerNode
from backend.app.schemas.itinerary import DayPlan, EstimatedCost, Itinerary, Visit
from backend.app.schemas.place import Candidates, Place
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import TravelConstraints, TripRequest, WeatherInfo


class StructuredModel(FakeMessagesListChatModel):
    """模拟结构化工具调用，仍通过真实 create_agent 和 ToolStrategy 执行。"""

    _inputs: list = PrivateAttr(default_factory=list)

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._inputs.append(messages)
        return super()._generate(messages, stop, run_manager, **kwargs)


@pytest.fixture
def trip_data():
    return {
        "trip_request": TripRequest(
            destination_city="杭州", days=1, start_date=date(2026, 10, 7)
        ),
        "candidates": Candidates(
            attractions=[
                Place(
                    id="test-poi", name="测试景点", location="120,30", category="景点"
                )
            ]
        ),
        "travel_constraints": TravelConstraints(
            weather=[WeatherInfo(date=date(2026, 10, 7), description="测试天气")],
            constraints=["一天行程"],
        ),
        "itinerary": Itinerary(
            days=[DayPlan(day=1, visits=[Visit(place_id="test-poi", stay_minutes=60)])],
            estimated_cost=EstimatedCost(),
        ),
        "review_result": ReviewResult(decision="pass"),
        "rule_issues": ["测试规则问题"],
    }


def structured_agent(response):
    model = StructuredModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": type(response).__name__,
                        "args": response.model_dump(mode="json"),
                        "id": "structured-result",
                    }
                ],
            )
        ]
    )
    agent = create_agent(model=model, response_format=ToolStrategy(type(response)))
    return agent, model


@pytest.mark.asyncio
@pytest.mark.parametrize("with_checkpointer", [False, True])
async def test_cached_agents_handoff_through_subgraphs_to_parent(
    trip_data, with_checkpointer, monkeypatch
):
    # 此测试只验证四个专业 Agent 的交接，需求理解由独立测试覆盖。
    monkeypatch.setattr(
        "backend.app.graph.builder.UnderstandNode", lambda model: lambda state: {}
    )
    fields = {
        "researcher": "candidates",
        "context_analyst": "travel_constraints",
        "planner": "itinerary",
        "reviewer": "review_result",
    }
    pairs = {role: structured_agent(trip_data[field]) for role, field in fields.items()}
    agents = {role: pair[0] for role, pair in pairs.items()}
    graph = build_trip_graph(
        agents, checkpointer=InMemorySaver() if with_checkpointer else None
    )
    message = HumanMessage(content="用户的原始需求")
    result = await graph.ainvoke(
        {
            "messages": [message],
            "trip_request": trip_data["trip_request"],
            "missing_fields": [],
            "revision_count": 0,
            "confirmed": True,
        },
        config={"configurable": {"thread_id": "agent-handoff"}},
        context=TravelBuddyContext(user_id=1, conversation_id="agent-handoff"),
    )

    for field in fields.values():
        assert result[field] == trip_data[field]
    assert result["messages"] == [message]
    assert "structured_response" not in result
    for pair in pairs.values():
        assert len(pair[1]._inputs) == 1

    for role in ("researcher", "context_analyst"):
        assert json.loads(pairs[role][1]._inputs[0][0].content) == (
            trip_data["trip_request"].model_dump(mode="json")
        )
    planner_payload = json.loads(pairs["planner"][1]._inputs[0][0].content)
    assert planner_payload == {
        "trip_request": trip_data["trip_request"].model_dump(mode="json"),
        "candidates": trip_data["candidates"].model_dump(mode="json"),
        "travel_constraints": trip_data["travel_constraints"].model_dump(mode="json"),
        "review_result": None,
        "itinerary": None,
    }
    reviewer_payload = json.loads(pairs["reviewer"][1]._inputs[0][0].content)
    assert reviewer_payload["days"] == trip_data["itinerary"].model_dump(mode="json")["days"]
    assert reviewer_payload["places"] == {"test-poi": "测试景点"}
    assert reviewer_payload["trip_request"] == planner_payload["trip_request"]
    assert reviewer_payload["rule_issues"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node_type", "field"),
    [
        (ResearchNode, "candidates"),
        (AnalyzeContextNode, "travel_constraints"),
        (PlanNode, "itinerary"),
        (ReviewNode, "review_result"),
    ],
)
async def test_nodes_forward_runtime_and_validate_output(trip_data, node_type, field):
    messages = [AIMessage(content="内部消息")]
    agent = AsyncMock()
    agent.ainvoke.return_value = {
        "messages": messages,
        "structured_response": trip_data[field].model_dump(mode="json"),
    }
    context = TravelBuddyContext(user_id=7, conversation_id="forward-context")
    config = {"configurable": {"thread_id": "forward-context"}, "tags": ["test"]}
    result = await node_type(agent)(trip_data, Runtime(context=context), config)

    assert result[field] == trip_data[field]
    assert result["messages"] == messages
    assert agent.ainvoke.await_args.kwargs == {"config": config, "context": context}
    payload = json.loads(agent.ainvoke.await_args.args[0]["messages"][0].content)
    if node_type is PlanNode:
        assert payload["itinerary"] == trip_data["itinerary"].model_dump(mode="json")
        assert payload["review_result"] == trip_data["review_result"].model_dump(
            mode="json"
        )
    if node_type is ReviewNode:
        assert payload["rule_issues"] == trip_data["rule_issues"]

    agent.ainvoke.return_value["structured_response"] = None
    expected_error = RuntimeError if node_type is PlanNode else ValidationError
    with pytest.raises(expected_error):
        await node_type(agent)(trip_data, Runtime(context=context), config)


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ["是否调整必去地点？", None])
async def test_review_question_returns_to_parent_and_clears_stale_value(
    trip_data, question
):
    review = ReviewResult(
        decision="needs_user" if question else "pass", clarification_question=question
    )
    agent, _ = structured_agent(review)
    subgraph = build_reviewer_graph(agent)
    context = TravelBuddyContext(user_id=1, conversation_id="review-question")
    result = await ReviewerNode(subgraph)(
        {**trip_data, "clarification_question": "过期问题"},
        Runtime(context=context),
        {},
    )
    assert result == {"review_result": review, "clarification_question": question}


def test_missing_agent_fails_when_building_parent():
    with pytest.raises(ValueError, match="缺少 Agent"):
        build_trip_graph({})
