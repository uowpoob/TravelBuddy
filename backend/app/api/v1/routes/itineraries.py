from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, get_session
from backend.app.models import User
from backend.app.schemas.itinerary import SavedItineraryDetail, SavedItineraryPublic
from backend.app.services.itineraries import get_user_itinerary, list_user_itineraries

router = APIRouter(prefix="/api/v1/itineraries", tags=["itineraries"])


@router.get("", response_model=list[SavedItineraryPublic])
async def list_itineraries(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SavedItineraryPublic]:
    try:
        records = await list_user_itineraries(session, user.id, offset, limit)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    return [SavedItineraryPublic.model_validate(item) for item in records]


@router.get("/{itinerary_id}", response_model=SavedItineraryDetail)
async def get_itinerary(
    itinerary_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SavedItineraryDetail:
    try:
        record = await get_user_itinerary(session, user.id, itinerary_id)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    if record is None:
        raise HTTPException(status_code=404, detail="行程不存在。")
    return SavedItineraryDetail.model_validate(record)
