from datetime import date
from uuid import uuid4

import pytest

from backend.app.core.runtime import loop_factory
from backend.app.schemas.itinerary import DayPlan, EstimatedCost, Itinerary, Visit
from backend.app.schemas.place import Candidates, Place
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import TravelConstraints, TripRequest


def pytest_asyncio_loop_factories():
    """Use the application's psycopg-compatible event loop for async tests."""
    return {"app": loop_factory}


@pytest.fixture
def confirmed_trip_state():
    return {
        "confirmed": True,
        "save_key": str(uuid4()),
        "trip_request": TripRequest(
            destination_city="杭州",
            start_date=date(2026, 10, 10),
            days=1,
            travelers=2,
            transport="步行",
        ),
        "itinerary": Itinerary(
            days=[DayPlan(day=1, visits=[Visit(place_id="test-poi", stay_minutes=60)])],
            estimated_cost=EstimatedCost(),
        ),
        "candidates": Candidates(
            attractions=[
                Place(
                    id="test-poi",
                    name="测试景点",
                    address="测试地址",
                    location="120.1,30.2",
                    category="attraction",
                )
            ]
        ),
        "travel_constraints": TravelConstraints(constraints=["测试约束"]),
        "review_result": ReviewResult(decision="pass"),
    }
