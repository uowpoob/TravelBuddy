from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, get_session
from backend.app.models import User
from backend.app.schemas.conversation import (
    ConversationCreate,
    ConversationCreated,
    ConversationMessagesOut,
    ConversationPublic,
    MessageCreate,
    MessageTurnOut,
)
from backend.app.schemas.deletion import DeletionImpact
from backend.app.schemas.planning import PlanningProgressOut
from backend.app.services.conversations import (
    create_conversation,
    get_user_conversation,
    list_user_conversations,
)
from backend.app.services.deletions import (
    conversation_deletion_impact,
    delete_conversation,
)
from backend.app.services.messages import ConversationChatService, ConversationError

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("/{conversation_id}/deletion-impact", response_model=DeletionImpact)
async def deletion_impact(
    conversation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeletionImpact:
    try:
        return await conversation_deletion_impact(
            session, user.id, str(conversation_id)
        )
    except ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None


@router.delete("/{conversation_id}", status_code=204)
async def remove_conversation(
    conversation_id: UUID,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    expected_itinerary_count: Annotated[int, Query(ge=0)],
    confirmed: bool = False,
    delete_itineraries: bool = False,
) -> Response:
    try:
        await delete_conversation(
            session,
            user.id,
            str(conversation_id),
            getattr(request.app.state, "trip_graph", None),
            confirmed=confirmed,
            delete_itineraries=delete_itineraries,
            expected_itinerary_count=expected_itinerary_count,
        )
    except ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="存在其他关联数据，未执行删除。请重新查看删除影响后再确认。",
        ) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    return Response(status_code=204)


def get_chat_service(request: Request) -> ConversationChatService:
    return ConversationChatService(
        getattr(request.app.state, "trip_graph", None),
        getattr(request.app.state, "session_factory", None),
    )


@router.get("/{conversation_id}/progress", response_model=PlanningProgressOut)
async def get_planning_progress(
    conversation_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    chat: Annotated[ConversationChatService, Depends(get_chat_service)],
) -> PlanningProgressOut:
    """读取会话当前节点状态；消息执行期间可独立查询。"""
    response.headers["Cache-Control"] = "no-store"
    try:
        return await chat.get_progress(session, user.id, str(conversation_id))
    except ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None


@router.post("", response_model=ConversationCreated, status_code=201)
async def create(
    payload: ConversationCreate,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    chat: Annotated[ConversationChatService, Depends(get_chat_service)],
) -> ConversationCreated:
    try:
        conversation, reused = await create_conversation(
            session, user.id, payload.title, chat
        )
    except ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    if reused:
        response.status_code = 200
    return ConversationCreated(
        **ConversationPublic.model_validate(conversation).model_dump(), reused=reused
    )


@router.get("", response_model=list[ConversationPublic])
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[ConversationPublic]:
    try:
        conversations = await list_user_conversations(session, user.id, offset, limit)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    return [ConversationPublic.model_validate(item) for item in conversations]


@router.get("/{conversation_id}", response_model=ConversationPublic)
async def get_conversation(
    conversation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationPublic:
    try:
        conversation = await get_user_conversation(
            session, user.id, str(conversation_id)
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在。")
    return ConversationPublic.model_validate(conversation)


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesOut)
async def list_messages(
    conversation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    chat: Annotated[ConversationChatService, Depends(get_chat_service)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ConversationMessagesOut:
    """校验归属后读取 checkpoint，按对话顺序返回用户消息和助手答复。"""
    try:
        return await chat.list_messages(
            session, user.id, str(conversation_id), offset, limit
        )
    except ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None


@router.post("/{conversation_id}/messages", response_model=MessageTurnOut)
async def send_message(
    conversation_id: UUID,
    payload: MessageCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    chat: Annotated[ConversationChatService, Depends(get_chat_service)],
) -> MessageTurnOut:
    """非流式发送或恢复消息，等待本轮暂停或完成后返回增量消息。"""
    try:
        return await chat.send_message(session, user.id, str(conversation_id), payload)
    except ConversationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
