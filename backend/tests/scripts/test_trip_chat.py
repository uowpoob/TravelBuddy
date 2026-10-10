from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from backend.app.graph.builder import build_trip_graph
from backend.app.schemas.structured_output import RequestUnderstanding
from backend.app.schemas.trip import TripRequest
from backend.app.services.itineraries import SavedItineraryResult
from backend.scripts.trip_chat import (
    ChatIdentity,
    ToolProgress,
    chat_loop,
    parse_args,
    safe_diagnostic,
)


def graph_and_factory(state, responses):
    agents = {}
    for role, field in (
        ("researcher", "candidates"),
        ("context_analyst", "travel_constraints"),
        ("planner", "itinerary"),
        ("reviewer", "review_result"),
    ):
        agent = AsyncMock()
        agent.ainvoke.return_value = {
            "messages": [],
            "structured_response": state[field],
        }
        agents[role] = agent
    extractor = AsyncMock()
    extractor.ainvoke.side_effect = responses
    model = MagicMock()
    model.with_structured_output.return_value = extractor
    graph = build_trip_graph(
        agents, checkpointer=InMemorySaver(), understand_model=model
    )
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=object())
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return graph, factory


def complete_extraction(state):
    return RequestUnderstanding(
        new_trip=False,
        updated_fields=[
            "destination_city",
            "start_date",
            "days",
            "travelers",
            "transport",
        ],
        trip_request=state["trip_request"],
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ["--once"],
        ["--message", "   "],
        ["--user-id", "0"],
        ["--timeout", "inf"],
        ["--recursion-limit", "0"],
        ["--conversation-id", str(uuid4())],
    ],
)
def test_cli_rejects_ambiguous_or_unbounded_arguments(arguments):
    with pytest.raises(SystemExit) as exc:
        parse_args(arguments)
    assert exc.value.code == 2


@pytest.mark.asyncio
async def test_cli_drives_clarification_confirmation_and_save(
    confirmed_trip_state, monkeypatch, capsys
):
    graph, factory = graph_and_factory(
        confirmed_trip_state,
        [
            RequestUnderstanding(
                new_trip=False,
                updated_fields=["destination_city"],
                trip_request=TripRequest(destination_city="杭州"),
            ),
            complete_extraction(confirmed_trip_state),
        ],
    )
    save = AsyncMock(return_value=SavedItineraryResult(95, 1))
    monkeypatch.setattr("backend.app.graph.nodes.save.save_confirmed_itinerary", save)
    answers = iter(["2026-10-10 出发，1 天，2 人，步行", "/state", "确认", "/quit"])
    identity = ChatIdentity(1, str(uuid4()))
    code = await chat_loop(
        graph,
        factory,
        identity,
        parse_args(["--message", "想去杭州"]),
        read_input=lambda prompt: next(answers),
    )
    assert code == 0
    save.assert_awaited_once()
    snapshot = await graph.aget_state(
        {"configurable": {"thread_id": identity.conversation_id}}
    )
    assert snapshot.values["saved_itinerary_id"] == 95
    output = capsys.readouterr().out
    for text in ("请补充", "测试景点", "地点调研", "规划行程", "行程 ID=95"):
        assert text in output


@pytest.mark.asyncio
async def test_once_stops_at_confirmation_without_saving(
    confirmed_trip_state, monkeypatch, capsys
):
    graph, factory = graph_and_factory(
        confirmed_trip_state, [complete_extraction(confirmed_trip_state)]
    )
    save = AsyncMock()
    monkeypatch.setattr("backend.app.graph.nodes.save.save_confirmed_itinerary", save)
    code = await chat_loop(
        graph,
        factory,
        ChatIdentity(1, str(uuid4())),
        parse_args(["--message", "杭州一日游", "--once"]),
    )
    assert code == 0
    save.assert_not_awaited()
    assert "是否接受当前行程" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_retry_continues_failed_save_without_leaking_error_text(
    confirmed_trip_state, monkeypatch, capsys
):
    graph, factory = graph_and_factory(
        confirmed_trip_state, [complete_extraction(confirmed_trip_state)]
    )
    save = AsyncMock(
        side_effect=[RuntimeError("password=do-not-leak"), SavedItineraryResult(95, 1)]
    )
    monkeypatch.setattr("backend.app.graph.nodes.save.save_confirmed_itinerary", save)
    answers = iter(["确认", "/retry", "/quit"])
    code = await chat_loop(
        graph,
        factory,
        ChatIdentity(1, str(uuid4())),
        parse_args(["--message", "杭州一日游"]),
        read_input=lambda prompt: next(answers),
    )
    assert code == 0
    assert save.await_count == 2
    assert (
        save.await_args_list[0].kwargs["save_key"]
        == save.await_args_list[1].kwargs["save_key"]
    )
    output = capsys.readouterr().out
    assert "RuntimeError" in output
    assert "do-not-leak" not in output
    assert "行程 ID=95" in output


@pytest.mark.asyncio
async def test_tool_progress_hides_arguments_results_and_error_urls(capsys):
    handler = ToolProgress()
    run_id = uuid4()
    await handler.on_tool_start({"name": "maps_weather"}, "key=secret", run_id=run_id)
    await handler.on_tool_error(
        RuntimeError("https://example.invalid?key=secret"), run_id=run_id
    )
    output = capsys.readouterr().out
    assert "maps_weather" in output
    assert "secret" not in output
    await handler.on_tool_start({"name": None}, "", run_id=uuid4())
    await handler.on_tool_start({"name": "Itinerary"}, "", run_id=uuid4())
    assert capsys.readouterr().out == ""


@pytest.mark.asyncio
async def test_failed_understand_explains_state_and_retries_original_input(
    confirmed_trip_state,
    capsys,
):
    graph, factory = graph_and_factory(
        confirmed_trip_state,
        [
            RuntimeError(
                "Thinking mode does not support this tool_choice; password=do-not-leak"
            ),
            RequestUnderstanding(
                new_trip=False,
                updated_fields=["destination_city"],
                trip_request=TripRequest(destination_city="杭州"),
            ),
        ],
    )
    identity = ChatIdentity(1, str(uuid4()))
    answers = iter(["/state", "/retry", "/quit"])
    code = await chat_loop(
        graph,
        factory,
        identity,
        parse_args(["--message", "我想去杭州玩", "--debug"]),
        read_input=lambda prompt: next(answers),
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "Thinking mode does not support this tool_choice" in output
    assert "尚未完成需求提取" in output
    assert "[失败节点] understand" in output
    assert "do-not-leak" not in output
    assert "test_trip_chat.py" in output or "understand.py" in output
    snapshot = await graph.aget_state(
        {"configurable": {"thread_id": identity.conversation_id}}
    )
    assert snapshot.values["trip_request"].destination_city == "杭州"
    assert snapshot.interrupts
    assert sum(message.type == "human" for message in snapshot.values["messages"]) == 1


def test_diagnostics_hide_config_secrets_urls_and_malformed_dsns(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-model-secret")
    monkeypatch.setenv("LANGGRAPH_PG_DSN", "invalid checkpoint DSN")
    monkeypatch.setenv(
        "DATABASE_DSN", "postgresql://tester:private-db-secret@localhost/test"
    )
    result = safe_diagnostic(
        RuntimeError(
            "HTTP 400: Thinking mode does not support this tool_choice; "
            "private-model-secret private-db-secret; "
            "https://example.invalid?key=private-amap-secret; password='a private password'; "
            "Authorization: Bearer private-bearer-token"
        )
    )
    assert "HTTP 400" in result
    assert "tool_choice" in result
    for secret in (
        "private-model-secret",
        "private-db-secret",
        "private-amap-secret",
        "a private password",
        "private-bearer-token",
    ):
        assert secret not in result
