from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import SavedItinerary
from backend.app.repositories.itineraries import ItineraryRepository
from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import (
    TravelConstraints,
    TripRequest,
    missing_request_fields,
)


class ItinerarySaveError(ValueError):
    """确认后的方案或保存上下文无效。"""


class ConversationAccessError(LookupError):
    """会话不存在，或不属于当前用户。"""


class SaveKeyConflictError(ItinerarySaveError):
    """同一保存标识被用于不同的方案。"""


@dataclass(frozen=True)
class SavedItineraryResult:
    id: int
    version: int


async def list_user_itineraries(
    session: AsyncSession, user_id: int, offset: int = 0, limit: int = 20
) -> list[SavedItinerary]:
    return await ItineraryRepository(session).list_by_user(user_id, offset, limit)


async def get_user_itinerary(
    session: AsyncSession, user_id: int, itinerary_id: int
) -> SavedItinerary | None:
    return await ItineraryRepository(session).get_owned_by_id(itinerary_id, user_id)


def _validate_model[Model: BaseModel](model: type[Model], value: object) -> Model:
    # 再次校验实例的字段，避免 model_copy(update=...) 绕过约束。
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    return model.model_validate(value)


def build_snapshot(
    *,
    trip_request: object,
    itinerary: object,
    candidates: object,
    travel_constraints: object = None,
    review_result: object = None,
) -> dict[str, Any]:
    request = _validate_model(TripRequest, trip_request)
    plan = _validate_model(Itinerary, itinerary)
    places = _validate_model(Candidates, candidates)
    constraints = (
        _validate_model(TravelConstraints, travel_constraints)
        if travel_constraints is not None
        else None
    )
    review = (
        _validate_model(ReviewResult, review_result)
        if review_result is not None
        else None
    )
    if missing_request_fields(request):
        raise ItinerarySaveError("旅行需求不完整，不能保存行程。")
    if [day.day for day in plan.days] != list(range(1, request.days + 1)):
        raise ItinerarySaveError("行程天数或每日编号与旅行需求不一致。")
    visits = [visit for day in plan.days for visit in day.visits]
    if not visits:
        raise ItinerarySaveError("不能保存没有任何活动的行程。")
    known_places = {
        place.id: place
        for place in places.attractions + places.restaurants + places.hotels
    }
    if any(
        visit.place_id not in known_places
        or not visit.place_id.strip()
        or not known_places[visit.place_id].name.strip()
        for visit in visits
    ):
        raise ItinerarySaveError("行程引用的地点信息缺失，不能保存。")
    if review is not None and review.decision != "pass":
        raise ItinerarySaveError("当前行程尚未通过审核，不能保存。")
    return {
        "title": f"{request.destination_city}{request.days}日游",
        "destination_city": request.destination_city,
        "start_date": request.start_date,
        "days": request.days,
        "trip_request": request.model_dump(mode="json"),
        "itinerary": plan.model_dump(mode="json"),
        "candidates": places.model_dump(mode="json"),
        "travel_constraints": constraints.model_dump(mode="json")
        if constraints
        else None,
        "review_result": review.model_dump(mode="json") if review else None,
    }


async def save_confirmed_itinerary(
    session: AsyncSession,
    *,
    user_id: int,
    conversation_id: str,
    save_key: str | None,
    trip_request: object,
    itinerary: object,
    candidates: object,
    travel_constraints: object = None,
    review_result: object = None,
) -> SavedItineraryResult:
    """锁定用户会话，复用同一保存请求或分配新版本；提交成功后才返回。

    session 专供此用例，调用前不能已有事务；外层代码不应另包 session.begin()。
    不依赖 State 中的 saved_itinerary_id，覆盖数据库已提交但 checkpoint 未更新的重试。
    """
    if type(user_id) is not int or user_id < 1:
        raise ItinerarySaveError("保存行程需要有效的用户身份。")
    try:
        conversation_id = str(UUID(conversation_id))
        save_key = str(UUID(save_key))
    except (ValueError, TypeError, AttributeError):
        raise ItinerarySaveError("会话或方案保存标识无效，请先完成规划。") from None
    snapshot = build_snapshot(
        trip_request=trip_request,
        itinerary=itinerary,
        candidates=candidates,
        travel_constraints=travel_constraints,
        review_result=review_result,
    )
    if session.in_transaction():
        raise ItinerarySaveError("Save 需要未开启事务的专用数据库 session。")
    repository = ItineraryRepository(session)
    async with session.begin():
        conversation = await repository.lock_owned_conversation(
            conversation_id, user_id
        )
        if conversation is None:
            raise ConversationAccessError("会话不存在或不属于当前用户。")
        existing = await repository.find_saved(conversation_id, save_key)
        if existing is not None:
            if any(
                getattr(existing, field) != value for field, value in snapshot.items()
            ):
                raise SaveKeyConflictError("同一保存标识对应的行程内容不一致。")
            result = SavedItineraryResult(existing.id, existing.version)
        else:
            version = await repository.next_version(conversation_id)
            record = await repository.insert_snapshot(
                conversation_id=conversation_id,
                save_key=save_key,
                version=version,
                snapshot=snapshot,
                conversation=conversation,
            )
            result = SavedItineraryResult(record.id, record.version)
    return result
