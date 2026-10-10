from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, get_session
from backend.app.models import User
from backend.app.schemas.deletion import DeletionImpact
from backend.app.schemas.itinerary import SavedItineraryDetail, SavedItineraryPublic
from backend.app.schemas.route import DayRoutes, RouteMode
from backend.app.services.deletions import delete_itinerary, itinerary_deletion_impact
from backend.app.services.itineraries import get_user_itinerary, list_user_itineraries
from backend.app.services.messages import ConversationError
from backend.app.services.routes import get_day_routes

router = APIRouter(prefix="/api/v1/itineraries", tags=["itineraries"])


@router.get("/{itinerary_id}/deletion-impact", response_model=DeletionImpact)
async def deletion_impact(
    itinerary_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeletionImpact:
    try:
        return await itinerary_deletion_impact(session, user.id, itinerary_id)
    except ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None


@router.delete("/{itinerary_id}", status_code=204)
async def remove_itinerary(
    itinerary_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    confirmed: bool = False,
) -> Response:
    try:
        await delete_itinerary(session, user.id, itinerary_id, confirmed=confirmed)
    except ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="这份行程存在其他关联数据，未执行删除。请重新查看删除影响后再确认。",
        ) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    return Response(status_code=204)


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


@router.get("/{itinerary_id}/routes", response_model=DayRoutes)
async def get_routes(
    itinerary_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    day: Annotated[int, Query(ge=1, le=5)],
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    mode: RouteMode | None = None,
) -> DayRoutes:
    try:
        record = await get_user_itinerary(session, user.id, itinerary_id)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    if record is None:
        raise HTTPException(status_code=404, detail="行程不存在。")
    snapshot = SavedItineraryDetail.model_validate(record)
    # 先读取并校验归属，再释放只读事务，不在供应商请求期间占用数据库连接。
    await session.rollback()
    client = getattr(request.app.state, "amap_route_client", None)
    if client is None:
        raise HTTPException(
            status_code=503, detail="地图服务配置未就绪，请配置后重启。"
        )
    try:
        return await get_day_routes(snapshot, day, client, mode)
    except LookupError:
        raise HTTPException(status_code=404, detail="该行程没有指定天数。") from None
