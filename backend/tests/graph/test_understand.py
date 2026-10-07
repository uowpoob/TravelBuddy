import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import PrivateAttr, ValidationError

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.understand import UnderstandNode
from backend.app.graph.routes import route_after_understand
from backend.app.graph.state import TripState
from backend.app.schemas.itinerary import DayPlan, EstimatedCost, Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.structured_output import RequestUnderstanding
from backend.app.schemas.trip import TravelConstraints, TripRequest


@pytest.fixture
def complete_request():
    return TripRequest(
        destination_city="杭州",
        departure_city="上海",
        days=2,
        start_date=date(2026, 10, 10),
        travelers=2,
        budget=3000,
        budget_scope="total",
        preferences=["慢节奏"],
        must_visit=["西湖"],
        transport="公共交通",
        additional_requirements=["第一天不要早起"],
    )


@pytest.fixture
def runtime():
    return Runtime(context=TravelBuddyContext(user_id=1, conversation_id="understand"))


def extraction_model(**values):
    extracted = RequestUnderstanding(**values)
    extractor = AsyncMock()
    extractor.ainvoke.return_value = extracted
    model = MagicMock()
    model.with_structured_output.return_value = extractor
    return model, extractor


def user_message(content, message_id="new-turn"):
    return HumanMessage(content=content, id=message_id)


@pytest.mark.asyncio
async def test_empty_input_requests_required_information_without_model(runtime):
    model = MagicMock()
    result = await UnderstandNode(model)({}, runtime, {})
    assert result["trip_request"] == TripRequest()
    assert result["missing_fields"] == [
        "destination_city",
        "start_date",
        "days",
        "travelers",
        "transport",
    ]
    assert "预算" not in result["clarification_question"]
    assert route_after_understand(result) == ["clarify"]
    assert result["revision_count"] == 0
    assert result["confirmed"] is False
    model.with_structured_output.assert_not_called()


@pytest.mark.asyncio
async def test_complete_structured_input_can_skip_model(complete_request, runtime):
    model = MagicMock()
    result = await UnderstandNode(model)(
        {"trip_request": complete_request}, runtime, {}
    )
    assert result["missing_fields"] == []
    assert result["clarification_question"] is None
    assert route_after_understand(result) == ["researcher", "context_analyst"]
    model.with_structured_output.assert_not_called()


@pytest.mark.asyncio
async def test_merges_only_declared_fields_and_resets_derived_state(
    complete_request, runtime
):
    model, extractor = extraction_model(
        new_trip=False,
        updated_fields=["days", "budget"],
        trip_request=TripRequest(days=3, budget=5000, destination_city="不应覆盖杭州"),
    )
    old_itinerary = Itinerary(days=[DayPlan(day=1)], estimated_cost=EstimatedCost())
    config = {"tags": ["requirements"], "configurable": {"thread_id": "understand"}}
    message = user_message("改为三天，总预算五千")
    result = await UnderstandNode(model)(
        {
            "messages": [message],
            "trip_request": complete_request,
            "itinerary": old_itinerary,
            "review_result": ReviewResult(decision="revise"),
            "revision_count": 2,
            "confirmed": True,
            "saved_itinerary_id": 10,
        },
        runtime,
        config,
    )
    assert result["trip_request"] == complete_request.model_copy(
        update={"days": 3, "budget": 5000}
    )
    assert result["itinerary"] is old_itinerary
    assert result["candidates"] == Candidates()
    assert result["travel_constraints"] == TravelConstraints()
    assert result["review_result"] is None
    assert result["revision_count"] == 0
    assert result["confirmed"] is False
    assert result["saved_itinerary_id"] is None
    assert result["last_understood_message_id"] == message.id
    assert "messages" not in result
    assert extractor.ainvoke.await_args.kwargs == {"config": config}
    payload = json.loads(extractor.ainvoke.await_args.args[0][1].content)
    assert payload["trip_request"] == complete_request.model_dump(mode="json")
    assert payload["latest_user_message"] == message.content
    assert payload["review_result"]["decision"] == "revise"
    date.fromisoformat(payload["current_date"])


@pytest.mark.asyncio
async def test_new_trip_does_not_inherit_old_conditions(complete_request, runtime):
    model, _ = extraction_model(
        new_trip=True,
        updated_fields=["destination_city"],
        trip_request=TripRequest(destination_city="成都"),
    )
    result = await UnderstandNode(model)(
        {
            "messages": [user_message("开始新的旅行，去成都")],
            "trip_request": complete_request,
            "itinerary": Itinerary(days=[], estimated_cost=EstimatedCost()),
        },
        runtime,
        {},
    )
    assert result["trip_request"] == TripRequest(destination_city="成都")
    assert result["itinerary"] is None
    assert "start_date" in result["missing_fields"]
    assert result["trip_request"].preferences == []


@pytest.mark.asyncio
async def test_explicit_clearing_and_list_changes(complete_request, runtime):
    model, _ = extraction_model(
        new_trip=False,
        updated_fields=[
            "budget",
            "must_visit",
            "preferences",
            "additional_requirements",
        ],
        trip_request=TripRequest(
            budget=None,
            must_visit=[],
            preferences=["慢节奏", "博物馆"],
            additional_requirements=["第一天不要早起", "第二天下午改为室内活动"],
        ),
    )
    result = await UnderstandNode(model)(
        {
            "messages": [
                user_message("取消预算上限和必去要求，增加博物馆，第二天下午安排室内")
            ],
            "trip_request": complete_request,
        },
        runtime,
        {},
    )
    request = result["trip_request"]
    assert request.budget is None
    assert request.must_visit == []
    assert request.preferences == ["慢节奏", "博物馆"]
    assert request.additional_requirements[-1] == "第二天下午改为室内活动"
    assert request.start_date == complete_request.start_date


@pytest.mark.asyncio
async def test_budget_scope_is_required_only_when_budget_is_present(
    complete_request, runtime
):
    state = {"trip_request": complete_request.model_copy(update={"budget_scope": None})}
    result = await UnderstandNode(MagicMock())(state, runtime, {})
    assert result["missing_fields"] == ["budget_scope"]
    assert "全体总额还是人均" in result["clarification_question"]
    state["trip_request"] = state["trip_request"].model_copy(update={"budget": None})
    result = await UnderstandNode(MagicMock())(state, runtime, {})
    assert result["missing_fields"] == []


@pytest.mark.asyncio
async def test_ambiguity_routes_to_clarify_even_with_complete_fields(
    complete_request, runtime
):
    model, _ = extraction_model(
        new_trip=False,
        updated_fields=[],
        trip_request=TripRequest(),
        clarification_question=" 您要调整当前行程，还是开始新旅行？ ",
    )
    result = await UnderstandNode(model)(
        {"messages": [user_message("换一个")], "trip_request": complete_request},
        runtime,
        {},
    )
    assert result["trip_request"] == complete_request
    assert result["missing_fields"] == []
    assert result["clarification_question"] == "您要调整当前行程，还是开始新旅行？"
    assert route_after_understand(result) == ["clarify"]


@pytest.mark.asyncio
async def test_latest_human_message_and_processed_message_guard(
    complete_request, runtime
):
    model, extractor = extraction_model(
        new_trip=False,
        updated_fields=["travelers"],
        trip_request=TripRequest(travelers=3),
    )
    message = user_message("改为三个人")
    state = {
        "messages": [
            HumanMessage(content="旧消息", id="old"),
            message,
            AIMessage(content="助手的回复，不是新增需求"),
        ],
        "trip_request": complete_request,
    }
    result = await UnderstandNode(model)(state, runtime, {})
    payload = json.loads(extractor.ainvoke.await_args.args[0][1].content)
    assert payload["latest_user_message"] == "改为三个人"
    state.update(result)
    assert await UnderstandNode(model)(state, runtime, {}) == {}
    assert extractor.ainvoke.await_count == 1


class UnderstandingModel(FakeMessagesListChatModel):
    _inputs: list = PrivateAttr(default_factory=list)

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._inputs.append(messages)
        return super()._generate(messages, stop, run_manager, **kwargs)


def understanding_response(**values):
    response = RequestUnderstanding(**values)
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "RequestUnderstanding",
                "id": "extraction",
                "args": response.model_dump(mode="json"),
            }
        ],
    )


@pytest.mark.asyncio
async def test_real_structured_model_parser_and_checkpointed_multi_turn_merge(
    complete_request,
):
    model = UnderstandingModel(
        responses=[
            understanding_response(
                new_trip=False,
                updated_fields=["destination_city"],
                trip_request=TripRequest(destination_city="杭州"),
            ),
            understanding_response(
                new_trip=False,
                updated_fields=["days", "start_date", "travelers", "transport"],
                trip_request=complete_request,
            ),
        ]
    )
    saver = InMemorySaver()
    context = TravelBuddyContext(user_id=1, conversation_id="multi-turn")
    config = {"configurable": {"thread_id": "multi-turn"}}

    def compile_graph():
        builder = StateGraph(TripState, context_schema=TravelBuddyContext)
        builder.add_node("understand", UnderstandNode(model))
        builder.add_edge(START, "understand")
        builder.add_edge("understand", END)
        return builder.compile(checkpointer=saver)

    result = await compile_graph().ainvoke(
        {"messages": [HumanMessage(content="想去杭州")]}, config=config, context=context
    )
    assert "days" in result["missing_fields"]
    graph = compile_graph()
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="十月十日，两天，两个人，公共交通")]},
        config=config,
        context=context,
    )
    assert result["trip_request"].destination_city == "杭州"
    assert result["trip_request"].days == 2
    assert result["trip_request"].start_date == date(2026, 10, 10)
    assert result["trip_request"].budget is None
    assert result["missing_fields"] == []
    assert len(result["messages"]) == 2
    assert (await graph.aget_state(config)).values["trip_request"] == result[
        "trip_request"
    ]
    previous = json.loads(model._inputs[1][1].content)
    assert previous["trip_request"]["destination_city"] == "杭州"


@pytest.mark.parametrize(
    "values",
    [
        {"days": 6},
        {"travelers": 0},
        {"budget": -1},
        {"budget_scope": "unknown"},
    ],
)
def test_invalid_extracted_values_are_rejected(values):
    with pytest.raises(ValidationError):
        RequestUnderstanding(
            new_trip=False, updated_fields=list(values), trip_request=values
        )
