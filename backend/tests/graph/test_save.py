from unittest.mock import AsyncMock

import pytest
from langgraph.runtime import Runtime
from pydantic import ValidationError

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.save import SaveNode
from backend.app.schemas.itinerary import DayPlan, EstimatedCost, Itinerary, Visit
from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.services.itineraries import ItinerarySaveError, build_snapshot


def snapshot_values(state):
    return {
        field: state[field]
        for field in (
            "trip_request",
            "itinerary",
            "candidates",
            "travel_constraints",
            "review_result",
        )
    }


def test_snapshot_preserves_unknown_cost_dates_and_place_details(confirmed_trip_state):
    state = confirmed_trip_state
    snapshot = build_snapshot(**snapshot_values(state))
    assert snapshot["title"] == "杭州1日游"
    assert snapshot["trip_request"]["start_date"] == "2026-10-10"
    assert snapshot["itinerary"]["estimated_cost"]["total"] is None
    place = snapshot["candidates"]["attractions"][0]
    assert (place["name"], place["address"], place["location"]) == (
        "测试景点",
        "测试地址",
        "120.1,30.2",
    )
    assert "confirmed" not in snapshot
    assert "save_key" not in snapshot


@pytest.mark.parametrize(
    "field", ["destination_city", "start_date", "days", "travelers", "transport"]
)
def test_missing_required_request_is_rejected(confirmed_trip_state, field):
    confirmed_trip_state["trip_request"] = confirmed_trip_state[
        "trip_request"
    ].model_copy(update={field: None})
    with pytest.raises(ItinerarySaveError, match="需求不完整"):
        build_snapshot(**snapshot_values(confirmed_trip_state))


@pytest.mark.parametrize(
    "days", [[], [DayPlan(day=2)], [DayPlan(day=1), DayPlan(day=1)]]
)
def test_day_count_and_order_must_match_request(confirmed_trip_state, days):
    confirmed_trip_state["itinerary"] = Itinerary(
        days=days, estimated_cost=EstimatedCost()
    )
    with pytest.raises(ItinerarySaveError, match="每日编号"):
        build_snapshot(**snapshot_values(confirmed_trip_state))


def test_empty_activity_plan_is_rejected(confirmed_trip_state):
    confirmed_trip_state["itinerary"] = Itinerary(
        days=[DayPlan(day=1)], estimated_cost=EstimatedCost()
    )
    with pytest.raises(ItinerarySaveError, match="没有任何活动"):
        build_snapshot(**snapshot_values(confirmed_trip_state))


def test_unknown_place_reference_is_rejected(confirmed_trip_state):
    confirmed_trip_state["candidates"] = Candidates()
    with pytest.raises(ItinerarySaveError, match="地点信息缺失"):
        build_snapshot(**snapshot_values(confirmed_trip_state))


@pytest.mark.parametrize("decision", ["revise", "needs_user"])
def test_unapproved_review_is_rejected(confirmed_trip_state, decision):
    confirmed_trip_state["review_result"] = ReviewResult(decision=decision)
    with pytest.raises(ItinerarySaveError, match="尚未通过审核"):
        build_snapshot(**snapshot_values(confirmed_trip_state))


def test_model_copy_cannot_bypass_validation(confirmed_trip_state):
    invalid_visit = Visit(place_id="test-poi", stay_minutes=60).model_copy(
        update={"stay_minutes": -1}
    )
    confirmed_trip_state["itinerary"] = Itinerary(
        days=[DayPlan(day=1, visits=[invalid_visit])], estimated_cost=EstimatedCost()
    )
    with pytest.raises(ValidationError):
        build_snapshot(**snapshot_values(confirmed_trip_state))


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmed", [None, False, 1, "yes"])
async def test_unconfirmed_state_never_calls_database(
    confirmed_trip_state, confirmed, monkeypatch
):
    save = AsyncMock()
    monkeypatch.setattr("backend.app.graph.nodes.save.save_confirmed_itinerary", save)
    state = {**confirmed_trip_state, "confirmed": confirmed}
    runtime = Runtime(context=TravelBuddyContext(user_id=1, conversation_id="test"))
    with pytest.raises(ItinerarySaveError, match="尚未确认"):
        await SaveNode()(state, runtime)
    save.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmed_state_requires_database(confirmed_trip_state):
    runtime = Runtime(context=TravelBuddyContext(user_id=1, conversation_id="test"))
    with pytest.raises(ItinerarySaveError, match="数据库 session"):
        await SaveNode()(confirmed_trip_state, runtime)
