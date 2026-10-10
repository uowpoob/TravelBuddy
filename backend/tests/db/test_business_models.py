"""PostgreSQL integration tests; each test rolls back every business row it writes.

Set TRAVELBUDDY_TEST_DATABASE_DSN to an already migrated PostgreSQL database.
Without this explicit opt-in, these tests skip instead of connecting to .env's database.
"""

import os
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models import Conversation, SavedItinerary, User
from backend.app.schemas.itinerary import DayPlan, EstimatedCost, Itinerary, Visit
from backend.app.schemas.place import Candidates, Place
from backend.app.schemas.trip import TripRequest


@pytest.fixture
def db_session():
    dsn = os.environ.get("TRAVELBUDDY_TEST_DATABASE_DSN", "").strip()
    if not dsn:
        pytest.skip("TRAVELBUDDY_TEST_DATABASE_DSN is not configured")
    settings = Settings(
        _env_file=None,
        database_dsn=dsn,
        DEEPSEEK_API_KEY="unused",
        DEEPSEEK_BASE_URL="https://example.invalid",
    )
    engine = create_engine(settings.database_url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                ) as session:
                    yield session
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def saved_itinerary(db_session):
    user = User(username=f"test-{uuid4().hex}", password_hash="test-password-hash")
    db_session.add(user)
    db_session.flush()
    conversation = Conversation(user_id=user.id)
    db_session.add(conversation)
    db_session.flush()
    request = TripRequest(
        destination_city="杭州",
        start_date=date(2026, 10, 10),
        days=1,
        travelers=2,
        transport="步行",
    )
    candidates = Candidates(
        attractions=[
            Place(
                id="test-poi-001",
                name="测试景点",
                location="120.1,30.2",
                category="attraction",
                address="测试地址",
            )
        ]
    )
    itinerary = Itinerary(
        days=[DayPlan(day=1, visits=[Visit(place_id="test-poi-001", stay_minutes=60)])],
        estimated_cost=EstimatedCost(),
    )
    row = SavedItinerary(
        conversation_id=conversation.id,
        version=1,
        title="杭州一日游",
        destination_city=request.destination_city,
        start_date=request.start_date,
        days=request.days,
        trip_request=request.model_dump(mode="json"),
        itinerary=itinerary.model_dump(mode="json"),
        candidates=candidates.model_dump(mode="json"),
    )
    db_session.add(row)
    db_session.flush()
    return row, conversation, user


def itinerary_values(row, **overrides):
    values = {
        "conversation_id": row.conversation_id,
        "version": row.version + 1,
        "title": row.title,
        "destination_city": row.destination_city,
        "start_date": row.start_date,
        "days": row.days,
        "trip_request": row.trip_request,
        "itinerary": row.itinerary,
        "candidates": row.candidates,
    }
    return {**values, **overrides}


def test_confirmed_snapshot_can_be_loaded_without_checkpoint(
    db_session, saved_itinerary
):
    row, conversation, user = saved_itinerary
    row_id, conversation_id, user_id = row.id, conversation.id, user.id
    # Commit the session savepoint, while keeping the outer test transaction open.
    db_session.commit()
    db_session.expire_all()
    restored = db_session.scalar(
        select(SavedItinerary)
        .join(Conversation)
        .where(SavedItinerary.id == row_id, Conversation.user_id == user_id)
    )
    assert restored.conversation_id == conversation_id
    assert isinstance(conversation_id, str)
    assert str(UUID(conversation_id)) == conversation_id
    assert conversation.title == "新旅行"
    assert restored.created_at.tzinfo is not None
    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None
    request = TripRequest.model_validate(restored.trip_request)
    itinerary = Itinerary.model_validate(restored.itinerary)
    candidates = Candidates.model_validate(restored.candidates)
    assert restored.start_date == request.start_date == date(2026, 10, 10)
    assert itinerary.estimated_cost.total is None
    visit = itinerary.days[0].visits[0]
    place = next(p for p in candidates.attractions if p.id == visit.place_id)
    assert (place.name, place.address, place.location) == (
        "测试景点",
        "测试地址",
        "120.1,30.2",
    )
    optional_fields_are_null = db_session.execute(
        text(
            "SELECT travel_constraints IS NULL, review_result IS NULL "
            "FROM itineraries WHERE id = :id"
        ),
        {"id": row_id},
    ).one()
    assert tuple(optional_fields_are_null) == (True, True)


def test_username_cannot_be_registered_twice(db_session, saved_itinerary):
    _, _, user = saved_itinerary
    with pytest.raises(IntegrityError) as exc, db_session.begin_nested():
        db_session.add(User(username=user.username, password_hash="test-hash"))
        db_session.flush()
    assert exc.value.orig.sqlstate == "23505"


def test_versions_preserve_history_and_reject_duplicate_save(
    db_session, saved_itinerary
):
    first, conversation, _ = saved_itinerary
    second = SavedItinerary(**itinerary_values(first, title="修改后的杭州行程"))
    db_session.add(second)
    db_session.flush()
    with pytest.raises(IntegrityError) as exc, db_session.begin_nested():
        db_session.add(SavedItinerary(**itinerary_values(first, version=1)))
        db_session.flush()
    assert exc.value.orig.sqlstate == "23505"
    versions = db_session.scalars(
        select(SavedItinerary)
        .where(SavedItinerary.conversation_id == conversation.id)
        .order_by(SavedItinerary.version)
    ).all()
    assert [(row.version, row.title) for row in versions] == [
        (1, "杭州一日游"),
        (2, "修改后的杭州行程"),
    ]


def test_separate_conversations_can_each_save_version_one(db_session, saved_itinerary):
    row, _, user = saved_itinerary
    other = Conversation(user_id=user.id)
    db_session.add(other)
    db_session.flush()
    separate = SavedItinerary(
        **itinerary_values(row, conversation_id=other.id, version=1)
    )
    db_session.add(separate)
    db_session.flush()
    assert separate.id != row.id


@pytest.mark.parametrize(
    ("field", "value", "sqlstate"),
    [
        ("days", 0, "23514"),
        ("days", 6, "23514"),
        ("version", 0, "23514"),
        ("title", "   ", "23514"),
        ("destination_city", "", "23514"),
        ("trip_request", None, "23502"),
        ("itinerary", [], "23514"),
        ("candidates", [], "23514"),
        ("travel_constraints", [], "23514"),
        ("review_result", [], "23514"),
    ],
)
def test_invalid_snapshot_is_rejected(
    db_session, saved_itinerary, field, value, sqlstate
):
    row, _, _ = saved_itinerary
    with pytest.raises(IntegrityError) as exc, db_session.begin_nested():
        db_session.add(SavedItinerary(**itinerary_values(row, **{field: value})))
        db_session.flush()
    assert exc.value.orig.sqlstate == sqlstate


@pytest.mark.parametrize("table", ["conversations", "itineraries"])
def test_foreign_keys_reject_missing_parent(db_session, saved_itinerary, table):
    row, _, _ = saved_itinerary
    invalid = (
        Conversation(user_id=-1)
        if table == "conversations"
        else SavedItinerary(**itinerary_values(row, conversation_id=str(uuid4())))
    )
    with pytest.raises(IntegrityError) as exc, db_session.begin_nested():
        db_session.add(invalid)
        db_session.flush()
    assert exc.value.orig.sqlstate == "23503"


@pytest.mark.parametrize("parent", ["user", "conversation"])
def test_deletion_does_not_silently_remove_history(db_session, saved_itinerary, parent):
    _, conversation, user = saved_itinerary
    with pytest.raises(IntegrityError) as exc, db_session.begin_nested():
        db_session.delete(user if parent == "user" else conversation)
        db_session.flush()
    assert exc.value.orig.sqlstate == "23503"
