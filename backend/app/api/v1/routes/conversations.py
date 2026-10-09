from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, get_session
from backend.app.models import User
from backend.app.schemas.conversation import (
    ConversationCreate,
    ConversationMessagesOut,
    ConversationPublic,
    MessageCreate,
    MessageTurnOut,
)
from backend.app.services.conversations import (
    create_conversation,
    get_user_conversation,
    list_user_conversations,
)
from backend.app.services.messages import ConversationChatService, ConversationError

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


def get_chat_service(request: Request) -> ConversationChatService:
    return ConversationChatService(
        getattr(request.app.state, "trip_graph", None),
        getattr(request.app.state, "session_factory", None),
    )


@router.post("", response_model=ConversationPublic, status_code=201)
async def create(
    payload: ConversationCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationPublic:
    try:
        conversation = await create_conversation(session, user.id, payload.title)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    return ConversationPublic.model_validate(conversation)


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
