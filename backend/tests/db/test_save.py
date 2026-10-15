"""Real PostgreSQL save tests; committed fixtures are removed by exact generated IDs."""

import asyncio
import os
from dataclasses import dataclass
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import SecretStr
from sqlalchemy import delete, event, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.config import Settings
from backend.app.db.session import create_engine
from backend.app.graph.builder import build_trip_graph
from backend.app.graph.checkpoints import open_checkpointer
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.confirm import ConfirmNode
from backend.app.graph.nodes.planner import PlannerNode
from backend.app.graph.nodes.save import SaveNode
from backend.app.graph.state import TripState
from backend.app.integrations.mcp import AmapMCPSettings
from backend.app.models import Conversation, SavedItinerary, User
from backend.app.schemas.structured_output import RequestUnderstanding
from backend.app.services.itineraries import (
    ConversationAccessError,
    ItinerarySaveError,
    SaveKeyConflictError,
)
from backend.scripts import trip_chat


@dataclass
class SaveDatabase:
    factory: async_sessionmaker
    user_id: int
    conversation_id: str

    def context(self, session, **overrides):
        return TravelBuddyContext(
            **{
                "user_id": self.user_id,
                "conversation_id": self.conversation_id,
                "db": session,
                **overrides,
            }
        )


@pytest_asyncio.fixture
async def save_database():
    dsn = os.environ.get("TRAVELBUDDY_TEST_DATABASE_DSN", "").strip()
    if not dsn:
        pytest.skip("TRAVELBUDDY_TEST_DATABASE_DSN is not configured")
    settings = Settings(
        _env_file=None,
        database_dsn=dsn,
        DEEPSEEK_API_KEY="unused",
        DEEPSEEK_BASE_URL="https://example.invalid",
    )
    engine = create_engine(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            user = User(username=f"save-test-{uuid4().hex}", password_hash="test-hash")
            session.add(user)
            await session.flush()
            conversation = Conversation(user_id=user.id)
            session.add(conversation)
            await session.flush()
            database = SaveDatabase(factory, user.id, conversation.id)
        try:
            yield database
        finally:
            async with factory() as session, session.begin():
                await session.execute(
                    delete(SavedItinerary).where(
                        SavedItinerary.conversation_id == database.conversation_id
                    )
                )
                await session.execute(
                    delete(Conversation).where(
                        Conversation.id == database.conversation_id
                    )
                )
                await session.execute(delete(User).where(User.id == database.user_id))
    finally:
        await engine.dispose()


async def save(database, state, **context_overrides):
    async with database.factory() as session:
        return await SaveNode()(
            state, Runtime(context=database.context(session, **context_overrides))
        )


async def records(database):
    async with database.factory() as session:
        return (
            await session.scalars(
                select(SavedItinerary)
                .where(SavedItinerary.conversation_id == database.conversation_id)
                .order_by(SavedItinerary.version)
            )
        ).all()


@pytest.mark.asyncio
async def test_save_commits_full_snapshot_before_return(
    save_database, confirmed_trip_state
):
    result = await save(save_database, confirmed_trip_state)
    rows = await records(save_database)  # a separate connection sees the committed row
    assert len(rows) == 1
    row = rows[0]
    assert result == {"saved_itinerary_id": row.id, "saved_itinerary_version": 1}
    assert row.save_key == confirmed_trip_state["save_key"]
    assert row.title == "杭州1日游"
    for field in (
        "trip_request",
        "itinerary",
        "candidates",
        "travel_constraints",
        "review_result",
    ):
        assert getattr(row, field) == confirmed_trip_state[field].model_dump(
            mode="json"
        )
    assert row.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_retry_without_checkpoint_result_reuses_saved_row(
    save_database, confirmed_trip_state
):
    first = await save(save_database, confirmed_trip_state)
    async with save_database.factory() as session:
        modified_at = await session.scalar(
            select(Conversation.updated_at).where(
                Conversation.id == save_database.conversation_id
            )
        )
    # Deliberately discard the first node output, as in a failure before checkpointing it.
    retry = await save(
        save_database, {**confirmed_trip_state, "saved_itinerary_id": 999999}
    )
    assert retry == first
    assert len(await records(save_database)) == 1
    async with save_database.factory() as session:
        assert (
            await session.scalar(
                select(Conversation.updated_at).where(
                    Conversation.id == save_database.conversation_id
                )
            )
            == modified_at
        )


@pytest.mark.asyncio
async def test_new_plan_key_creates_next_version_without_overwriting(
    save_database, confirmed_trip_state
):
    first = await save(save_database, confirmed_trip_state)
    changed = {
        **confirmed_trip_state,
        "save_key": str(uuid4()),
        "itinerary": confirmed_trip_state["itinerary"].model_copy(
            update={"notes": ["新方案"]}
        ),
    }
    second = await save(save_database, changed)
    assert second["saved_itinerary_version"] == 2
    assert second["saved_itinerary_id"] != first["saved_itinerary_id"]
    rows = await records(save_database)
    assert rows[0].itinerary["notes"] == []
    assert rows[1].itinerary["notes"] == ["新方案"]


@pytest.mark.asyncio
async def test_reused_key_with_changed_content_fails_without_overwrite(
    save_database, confirmed_trip_state
):
    await save(save_database, confirmed_trip_state)
    changed = {
        **confirmed_trip_state,
        "itinerary": confirmed_trip_state["itinerary"].model_copy(
            update={"notes": ["不能覆盖"]}
        ),
    }
    with pytest.raises(SaveKeyConflictError):
        await save(save_database, changed)
    rows = await records(save_database)
    assert len(rows) == 1
    assert rows[0].itinerary["notes"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_context", ["user", "conversation"])
async def test_cannot_save_into_another_or_missing_conversation(
    save_database, confirmed_trip_state, wrong_context
):
    overrides = (
        {"user_id": save_database.user_id + 1}
        if wrong_context == "user"
        else {"conversation_id": str(uuid4())}
    )
    with pytest.raises(ConversationAccessError):
        await save(save_database, confirmed_trip_state, **overrides)
    assert await records(save_database) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("same_key", [True, False])
async def test_concurrent_saves_serialize_version_allocation(
    save_database, confirmed_trip_state, same_key
):
    states = [
        {
            **confirmed_trip_state,
            "save_key": confirmed_trip_state["save_key"] if same_key else str(uuid4()),
        }
        for _ in range(3)
    ]
    results = await asyncio.gather(*(save(save_database, state) for state in states))
    rows = await records(save_database)
    if same_key:
        assert len(rows) == 1
        assert results[0] == results[1] == results[2]
    else:
        assert [row.version for row in rows] == [1, 2, 3]
        assert len({result["saved_itinerary_id"] for result in results}) == 3


@pytest.mark.asyncio
async def test_commit_failure_rolls_back_and_returns_no_success(
    save_database, confirmed_trip_state
):
    async with save_database.factory() as session:

        def fail_commit(_):
            raise RuntimeError("simulated commit failure")

        event.listen(session.sync_session, "before_commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated commit failure"):
            await SaveNode()(
                confirmed_trip_state, Runtime(context=save_database.context(session))
            )
        assert not session.in_transaction()
    assert await records(save_database) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("save_key", [None, "not-a-uuid"])
async def test_save_refuses_to_generate_a_new_key_during_retry(
    save_database, confirmed_trip_state, save_key
):
    with pytest.raises(ItinerarySaveError, match="保存标识无效"):
        await save(save_database, {**confirmed_trip_state, "save_key": save_key})
    assert await records(save_database) == []


def confirmation_graph(saver, planner, save_node):
    builder = StateGraph(TripState, context_schema=TravelBuddyContext)
    builder.add_node("planner", PlannerNode(planner))
    builder.add_node("confirm", ConfirmNode())
    builder.add_node("save", save_node)
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "confirm")
    builder.add_conditional_edges(
        "confirm", lambda state: "save" if state["confirmed"] else END
    )
    builder.add_edge("save", END)
    return builder.compile(checkpointer=saver)


class FailAfterCommittedSave:
    async def __call__(self, state: TripState, runtime: Runtime[TravelBuddyContext]):
        await SaveNode()(state, runtime)
        raise RuntimeError("simulated failure after database commit")


@pytest.mark.asyncio
async def test_confirm_pause_and_graph_rebuild_retry_after_committed_save(
    save_database, confirmed_trip_state
):
    saver = InMemorySaver()
    planner = AsyncMock()
    planner.ainvoke.return_value = {"itinerary": confirmed_trip_state["itinerary"]}
    graph = confirmation_graph(saver, planner, FailAfterCommittedSave())
    config = {"configurable": {"thread_id": save_database.conversation_id}}
    async with save_database.factory() as session:
        paused = await graph.ainvoke(
            confirmed_trip_state, config=config, context=save_database.context(session)
        )
    assert paused["__interrupt__"][0].value["type"] == "confirm"
    stable_key = paused["save_key"]
    async with save_database.factory() as session:
        with pytest.raises(RuntimeError, match="failure after database commit"):
            await graph.ainvoke(
                Command(resume="确认"),
                config=config,
                context=save_database.context(session),
            )
    committed = (await records(save_database))[0]
    assert committed.save_key == stable_key
    graph = confirmation_graph(saver, planner, SaveNode())
    async with save_database.factory() as session:
        result = await graph.ainvoke(
            None, config=config, context=save_database.context(session)
        )
    assert result["save_key"] == stable_key
    assert result["saved_itinerary_id"] == committed.id
    assert result["saved_itinerary_version"] == 1
    assert len(await records(save_database)) == 1
    planner.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_cli_reopens_pg_checkpoint_and_saves_with_mock_agents(
    save_database, confirmed_trip_state, monkeypatch, capsys
):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    settings = Settings(
        _env_file=None,
        database_dsn=os.environ["TRAVELBUDDY_TEST_DATABASE_DSN"],
        LANGGRAPH_PG_DSN=os.environ["TRAVELBUDDY_TEST_DATABASE_DSN"],
        DEEPSEEK_API_KEY="unused",
        DEEPSEEK_BASE_URL="https://example.invalid",
        GD_API_KEY="unused",
    )
    # Explicit test setup; the actual CLI never creates checkpoint tables implicitly.
    async with open_checkpointer(settings) as saver:
        await saver.setup()
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
            "structured_response": confirmed_trip_state[field],
        }
        agents[role] = agent
    extractor = AsyncMock()
    extractor.ainvoke.return_value = RequestUnderstanding(
        new_trip=False,
        updated_fields=[
            "destination_city",
            "start_date",
            "days",
            "travelers",
            "transport",
        ],
        trip_request=confirmed_trip_state["trip_request"],
    )
    model = MagicMock()
    model.with_structured_output.return_value = extractor
    monkeypatch.setattr(trip_chat, "Settings", lambda: settings)
    monkeypatch.setattr(
        trip_chat,
        "AmapMCPSettings",
        lambda: AmapMCPSettings(
            _env_file=None, api_key=SecretStr("unused"), redis_url=SecretStr("")
        ),
    )
    monkeypatch.setattr(
        trip_chat, "AmapMCPClient", lambda config: SimpleNamespace(close=AsyncMock())
    )
    monkeypatch.setattr(trip_chat, "build_agents", AsyncMock(return_value=agents))
    monkeypatch.setattr(
        trip_chat,
        "build_trip_graph",
        lambda agents, checkpointer, **kwargs: build_trip_graph(
            agents, checkpointer=checkpointer, understand_model=model, **kwargs
        ),
    )
    created_conversations = set()
    prepare = trip_chat.prepare_conversation

    async def track_conversation(factory, args):
        identity = await prepare(factory, args)
        created_conversations.add(identity.conversation_id)
        return identity

    monkeypatch.setattr(trip_chat, "prepare_conversation", track_conversation)
    try:
        assert (
            await trip_chat.main(
                trip_chat.parse_args(
                    [
                        "--user-id",
                        str(save_database.user_id),
                        "--message",
                        "杭州一日游",
                        "--once",
                    ]
                )
            )
            == 0
        )
        conversation_id = next(iter(created_conversations))
        async with open_checkpointer(settings) as saver:
            graph = build_trip_graph(agents, checkpointer=saver, understand_model=model)
            snapshot = await graph.aget_state(
                {"configurable": {"thread_id": conversation_id}}
            )
            assert snapshot.interrupts[0].value["type"] == "confirm"
            stable_key = snapshot.values["save_key"]
        assert (
            await trip_chat.main(
                trip_chat.parse_args(
                    [
                        "--user-id",
                        str(save_database.user_id),
                        "--conversation-id",
                        conversation_id,
                        "--message",
                        "确认",
                        "--once",
                    ]
                )
            )
            == 0
        )
        async with save_database.factory() as session:
            row = await session.scalar(
                select(SavedItinerary).where(
                    SavedItinerary.conversation_id == conversation_id
                )
            )
            assert row.save_key == stable_key
            assert row.version == 1
        extractor.ainvoke.assert_awaited_once()
        assert "[已保存]" in capsys.readouterr().out
    finally:
        for conversation_id in created_conversations:
            async with open_checkpointer(settings) as saver:
                await saver.adelete_thread(conversation_id)
            async with save_database.factory() as session, session.begin():
                await session.execute(
                    delete(SavedItinerary).where(
                        SavedItinerary.conversation_id == conversation_id
                    )
                )
                await session.execute(
                    delete(Conversation).where(Conversation.id == conversation_id)
                )
