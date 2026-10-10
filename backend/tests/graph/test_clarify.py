import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import ValidationError

from backend.app.graph.builder import build_trip_graph
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.clarify import ClarifyNode
from backend.app.graph.nodes.understand import UnderstandNode
from backend.app.graph.routes import route_after_understand
from backend.app.graph.state import TripState
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.structured_output import RequestUnderstanding
from backend.app.schemas.trip import TripRequest


def compile_clarification_graph(saver, model=None):
    builder = StateGraph(TripState, context_schema=TravelBuddyContext)
    builder.add_node("clarify", ClarifyNode())
    if model is None:
        builder.add_edge(START, "clarify")
        builder.add_edge("clarify", END)
    else:
        builder.add_node("understand", UnderstandNode(model))
        builder.add_edge(START, "understand")
        builder.add_conditional_edges(
            "understand",
            lambda state: (
                "clarify" if route_after_understand(state) == ["clarify"] else END
            ),
            {"clarify": "clarify", END: END},
        )
        builder.add_edge("clarify", "understand")
    return builder.compile(checkpointer=saver)


@pytest.fixture
def context():
    return TravelBuddyContext(user_id=1, conversation_id="clarify")


@pytest.fixture
def config():
    return {"configurable": {"thread_id": "clarify"}}


@pytest.fixture
def complete_request():
    return TripRequest(
        destination_city="杭州",
        start_date=date(2026, 10, 10),
        days=2,
        travelers=2,
        transport="公共交通",
    )


def extraction_model(*responses):
    extractor = AsyncMock()
    extractor.ainvoke.side_effect = responses
    model = MagicMock()
    model.with_structured_output.return_value = extractor
    return model, extractor


@pytest.mark.asyncio
async def test_missing_fields_pause_rebuild_and_multi_turn_resume(
    complete_request, config, context
):
    model, extractor = extraction_model(
        RequestUnderstanding(
            new_trip=False,
            updated_fields=["destination_city"],
            trip_request=TripRequest(destination_city="杭州"),
        ),
        RequestUnderstanding(
            new_trip=False,
            updated_fields=["days", "start_date"],
            trip_request=TripRequest(days=2, start_date=date(2026, 10, 10)),
        ),
        RequestUnderstanding(
            new_trip=False,
            updated_fields=["travelers", "transport"],
            trip_request=TripRequest(travelers=2, transport="公共交通"),
        ),
    )
    saver = InMemorySaver()
    graph = compile_clarification_graph(saver, model)
    original = HumanMessage(content="想去杭州")
    result = await graph.ainvoke(
        {"messages": [original]}, config=config, context=context
    )
    first_question = result["__interrupt__"][0].value["question"]
    assert result["__interrupt__"][0].value["missing_fields"] == [
        "start_date",
        "days",
        "travelers",
        "transport",
    ]
    assert result["messages"] == [original]
    assert (await graph.aget_state(config)).next == ("clarify",)
    assert extractor.ainvoke.await_count == 1

    # 重建图后复用 saver 与 thread_id，恢复暂停的节点。
    graph = compile_clarification_graph(saver, model)
    result = await graph.ainvoke(
        Command(resume="十月十日，两天"), config=config, context=context
    )
    assert result["missing_fields"] == ["travelers", "transport"]
    second_question = result["__interrupt__"][0].value["question"]
    assert [(message.type, message.content) for message in result["messages"]] == [
        ("human", "想去杭州"),
        ("ai", first_question),
        ("human", "十月十日，两天"),
    ]
    result = await graph.ainvoke(
        Command(resume=" 两个人，公共交通 "), config=config, context=context
    )
    assert result["trip_request"] == complete_request
    assert result["missing_fields"] == []
    assert result["clarification_question"] is None
    assert not result.get("__interrupt__")
    assert (await graph.aget_state(config)).next == ()
    assert extractor.ainvoke.await_count == 3
    assert [message.content for message in result["messages"][-2:]] == [
        second_question,
        "两个人，公共交通",
    ]
    assert len({message.id for message in result["messages"]}) == 5
    payload = json.loads(extractor.ainvoke.await_args.args[0][1].content)
    assert payload["latest_user_message"] == "两个人，公共交通"
    assert payload["recent_messages"][-2] == {"role": "ai", "content": second_question}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "question_fragment"),
    [
        ({"clarification_question": " 预算是总额还是人均？ "}, "预算是总额还是人均？"),
        ({"missing_fields": ["budget_scope"]}, "预算是全体总额还是人均"),
        (
            {
                "review_result": ReviewResult(
                    decision="needs_user",
                    clarification_question="增加预算还是减少景点？",
                )
            },
            "增加预算还是减少景点？",
        ),
        (
            {
                "review_result": ReviewResult(
                    decision="revise", issues=["费用超过预算", "每天时间安排过满"]
                ),
                "revision_count": 2,
            },
            "费用超过预算\n每天时间安排过满",
        ),
        ({"clarification_question": "   "}, "请说明希望调整哪些条件或如何取舍"),
    ],
)
async def test_questions_and_review_fallbacks_pause_without_mutating_state(
    state, question_fragment, config, context
):
    graph = compile_clarification_graph(InMemorySaver())
    original = HumanMessage(content="原始需求")
    result = await graph.ainvoke(
        {**state, "messages": [original]}, config=config, context=context
    )
    payload = result["__interrupt__"][0].value
    assert payload["type"] == "clarify"
    assert question_fragment in payload["question"]
    json.dumps(payload, ensure_ascii=False)
    assert result["messages"] == [original]
    review = state.get("review_result")
    assert payload["issues"] == (review.issues if review else [])

    result = await graph.ainvoke(
        Command(resume="增加预算"), config=config, context=context
    )
    assert len(result["messages"]) == 3
    assert isinstance(result["messages"][-2], AIMessage)
    assert result["messages"][-2].content == payload["question"]
    assert isinstance(result["messages"][-1], HumanMessage)
    assert result["messages"][-1].content == "增加预算"
    for field, value in state.items():
        assert result[field] == value


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["", " \n ", True, 123, {"answer": "增加预算"}, []])
async def test_invalid_answers_remain_paused_until_valid_text(answer, config, context):
    graph = compile_clarification_graph(InMemorySaver())
    await graph.ainvoke(
        {"clarification_question": "人数是多少？"}, config=config, context=context
    )
    with pytest.raises(ValidationError):
        await graph.ainvoke(Command(resume=answer), config=config, context=context)
    snapshot = await graph.aget_state(config)
    assert snapshot.values["messages"] == []
    assert snapshot.next == ("clarify",)

    result = await graph.ainvoke(Command(resume="2 人"), config=config, context=context)
    assert not result.get("__interrupt__")
    assert [message.content for message in result["messages"]] == [
        "人数是多少？",
        "2 人",
    ]


@pytest.mark.asyncio
async def test_user_choice_is_reunderstood_with_review_context(
    complete_request, config, context
):
    review = ReviewResult(
        decision="needs_user",
        issues=["费用超过预算"],
        clarification_question="增加预算还是减少景点？",
    )
    model, extractor = extraction_model(
        RequestUnderstanding(
            new_trip=False,
            updated_fields=["budget", "budget_scope"],
            trip_request=TripRequest(budget=5000, budget_scope="total"),
        )
    )
    builder = StateGraph(TripState, context_schema=TravelBuddyContext)
    builder.add_node("clarify", ClarifyNode())
    builder.add_node("understand", UnderstandNode(model))
    builder.add_edge(START, "clarify")
    builder.add_edge("clarify", "understand")
    builder.add_edge("understand", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    await graph.ainvoke(
        {"trip_request": complete_request, "review_result": review},
        config=config,
        context=context,
    )
    result = await graph.ainvoke(
        Command(resume="总预算改为五千"), config=config, context=context
    )
    assert result["trip_request"] == complete_request.model_copy(
        update={"budget": 5000, "budget_scope": "total"}
    )
    assert result["review_result"] is None
    payload = json.loads(extractor.ainvoke.await_args.args[0][1].content)
    assert payload["review_result"] == review.model_dump(mode="json")
    assert payload["recent_messages"][-2]["content"] == review.clarification_question


@pytest.mark.asyncio
async def test_parent_graph_pauses_before_agents_and_isolates_threads(context):
    agents = {
        role: AsyncMock()
        for role in ("researcher", "context_analyst", "planner", "reviewer")
    }
    graph = build_trip_graph(
        agents, checkpointer=InMemorySaver(), understand_model=MagicMock()
    )
    for thread in ("first", "second"):
        result = await graph.ainvoke(
            {"trip_request": TripRequest(destination_city=thread)},
            config={"configurable": {"thread_id": thread}},
            context=context,
        )
        assert result["__interrupt__"][0].value["type"] == "clarify"
    for agent in agents.values():
        agent.ainvoke.assert_not_awaited()
    first = await graph.aget_state({"configurable": {"thread_id": "first"}})
    second = await graph.aget_state({"configurable": {"thread_id": "second"}})
    assert first.values["trip_request"].destination_city == "first"
    assert second.values["trip_request"].destination_city == "second"
    assert first.tasks[0].interrupts[0].id != second.tasks[0].interrupts[0].id
