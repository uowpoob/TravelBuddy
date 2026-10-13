from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime
from pydantic import SecretStr
from redis.exceptions import ConnectionError

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.researcher import ResearcherNode
from backend.app.graph.nodes.understand import UnderstandNode
from backend.app.integrations.mcp.config import AmapMCPSettings
from backend.app.integrations.research_cache import ResearchCandidatesCache
from backend.app.schemas.place import Candidates, Place
from backend.app.schemas.structured_output import RequestUnderstanding
from backend.app.schemas.trip import TripRequest


def cache():
    return ResearchCandidatesCache(
        AmapMCPSettings(_env_file=None, redis_url=SecretStr("redis://127.0.0.1:6379/0"))
    )


def request(**changes):
    return TripRequest(
        destination_city="杭州",
        days=1,
        start_date=date(2026, 10, 14),
        travelers=2,
        transport="步行",
        **changes,
    )


def candidates(poi="fresh"):
    return Candidates(
        attractions=[
            Place(id=poi, name="西湖", location="120.1,30.2", category="风景名胜")
        ]
    )


def test_key_normalizes_order_and_only_known_pace_classification():
    storage = cache()
    a = request(
        preferences=["本地美食", "西湖", "节奏轻松"],
        additional_requirements=["不需要住宿"],
    )
    b = request(
        preferences=[" 西湖 ", "本地美食"],
        additional_requirements=["节奏轻松", "不需要住宿", "不需要住宿"],
    )
    assert storage.key_for(a) == storage.key_for(b)
    assert storage.key_for(request(preferences=["室内活动"])) != storage.key_for(
        request(additional_requirements=["室内活动"])
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"destination_city": "苏州"},
        {"days": 2},
        {"start_date": date(2026, 10, 15)},
        {"travelers": 3},
        {"transport": "公交"},
        {"budget": 1000, "budget_scope": "total"},
        {"preferences": ["历史文化"]},
        {"must_visit": ["灵隐寺"]},
        {"additional_requirements": ["需要酒店"]},
    ],
)
def test_changed_requirements_do_not_share_candidates(changes):
    storage = cache()
    original = request()
    assert storage.key_for(original) != storage.key_for(
        original.model_copy(update=changes)
    )


@pytest.mark.asyncio
async def test_cache_hit_skips_research_and_history_does_not_pollute_cache(monkeypatch):
    storage = cache()
    memory = {}

    async def get(key):
        return memory.get(key)

    async def set_value(key, value):
        memory[key] = value

    monkeypatch.setattr(storage, "get", get)
    monkeypatch.setattr(storage, "set", set_value)
    graph = SimpleNamespace(
        ainvoke=AsyncMock(return_value={"candidates": candidates()})
    )
    node = ResearcherNode(graph, storage)
    runtime = Runtime(context=TravelBuddyContext(user_id=1, conversation_id="first"))
    state = {
        "trip_request": request(),
        "candidates": candidates("old"),
        "itinerary": SimpleNamespace(
            days=[SimpleNamespace(visits=[SimpleNamespace(place_id="old")])]
        ),
    }
    first = await node(state, runtime, {})
    assert {p.id for p in first["candidates"].attractions} == {"fresh", "old"}
    second = await node({"trip_request": request()}, runtime, {})
    assert [p.id for p in second["candidates"].attractions] == ["fresh"]
    graph.ainvoke.assert_awaited_once()
    second["candidates"].attractions[0].name = "changed"
    assert (await storage.get_candidates(request())).attractions[0].name == "西湖"
    assert second["research_required"] is False
    await storage.close()


@pytest.mark.asyncio
async def test_corrupt_or_empty_cached_candidates_trigger_real_research(monkeypatch):
    storage = cache()
    graph = SimpleNamespace(
        ainvoke=AsyncMock(return_value={"candidates": candidates()})
    )
    node = ResearcherNode(graph, storage)
    runtime = Runtime(context=TravelBuddyContext(user_id=1, conversation_id="fallback"))
    monkeypatch.setattr(storage, "set", AsyncMock())
    for payload in (
        "invalid-json",
        Candidates().model_dump_json(),
        candidates()
        .model_copy(
            update={
                "attractions": [
                    Place(id="x", name="x", location="nan,30", category="景点")
                ]
            }
        )
        .model_dump_json(),
    ):
        monkeypatch.setattr(storage, "get", AsyncMock(return_value=payload))
        assert (await node({"trip_request": request()}, runtime, {}))[
            "candidates"
        ] == candidates()
    assert graph.ainvoke.await_count == 3
    await storage.close()


@pytest.mark.asyncio
async def test_redis_outage_does_not_block_research(monkeypatch):
    storage = cache()
    monkeypatch.setattr(storage._redis, "get", AsyncMock(side_effect=ConnectionError()))
    monkeypatch.setattr(storage._redis, "set", AsyncMock(side_effect=ConnectionError()))
    graph = SimpleNamespace(
        ainvoke=AsyncMock(return_value={"candidates": candidates()})
    )
    node = ResearcherNode(graph, storage)
    result = await node(
        {"trip_request": request()},
        Runtime(context=TravelBuddyContext(user_id=1, conversation_id="outage")),
        {},
    )
    assert result["candidates"] == candidates()
    graph.ainvoke.assert_awaited_once()
    await storage.close()


@pytest.mark.asyncio
async def test_empty_results_and_disabled_cache_are_not_stored(monkeypatch):
    storage = cache()
    writer = AsyncMock()
    monkeypatch.setattr(storage, "set", writer)
    await storage.set_candidates(request(), Candidates())
    writer.assert_not_awaited()
    await storage.close()
    disabled = ResearchCandidatesCache(
        AmapMCPSettings(_env_file=None, research_cache_enabled=False)
    )
    assert disabled.key_for(request()) is None
    assert await disabled.get_candidates(request()) is None
    await disabled.close()


def test_full_user_history_handles_extraction_noise_but_changes_invalidate():
    storage = cache()
    original = request(preferences=["西湖"], additional_requirements=["不需要住宿"])
    noisy = original.model_copy(
        update={"additional_requirements": ["不需要住宿", "由助手合理安排其他细节"]}
    )
    messages = ["杭州1天，喜欢西湖，不需要住宿"]
    assert storage.key_for(original) != storage.key_for(noisy)
    assert storage.key_for(original, messages) == storage.key_for(noisy, messages)
    assert storage.key_for(original, messages) != storage.key_for(
        original, [*messages, "只去室内地点"]
    )
    assert storage.key_for(original, messages) != storage.key_for(
        original.model_copy(update={"days": 2}), messages
    )


@pytest.mark.asyncio
async def test_explicit_refresh_bypasses_cache_and_is_reset(monkeypatch):
    storage = cache()
    reader = AsyncMock(return_value=candidates("cached"))
    monkeypatch.setattr(storage, "get_candidates", reader)
    monkeypatch.setattr(storage, "set_candidates", AsyncMock())
    graph = SimpleNamespace(
        ainvoke=AsyncMock(return_value={"candidates": candidates()})
    )
    runtime = Runtime(context=TravelBuddyContext(user_id=1, conversation_id="refresh"))
    result = await ResearcherNode(graph, storage)(
        {"trip_request": request(), "research_cache_bypass": True}, runtime, {}
    )
    reader.assert_not_awaited()
    graph.ainvoke.assert_awaited_once()
    assert result["research_cache_bypass"] is False
    await storage.close()


@pytest.mark.asyncio
async def test_understand_refresh_bypasses_only_when_replacing_existing_candidates():
    extractor = AsyncMock()
    extractor.ainvoke.return_value = RequestUnderstanding(
        new_trip=False,
        refresh_candidates=True,
        trip_request=request(),
        updated_fields=[],
    )
    model = MagicMock()
    model.with_structured_output.return_value = extractor
    runtime = Runtime(
        context=TravelBuddyContext(user_id=1, conversation_id="refresh-understand")
    )
    for previous, expected in ((candidates(), True), (Candidates(), False)):
        state = {
            "trip_request": request(),
            "messages": [HumanMessage(content="换一批", id="refresh")],
            "candidates": previous,
        }
        result = await UnderstandNode(model)(state, runtime, {})
        assert result["research_cache_bypass"] is expected
