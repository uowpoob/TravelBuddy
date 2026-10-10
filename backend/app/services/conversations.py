from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Conversation
from backend.app.repositories.conversations import ConversationRepository


async def create_conversation(
    session: AsyncSession, user_id: int, title: str
) -> tuple[Conversation, bool]:
    # 鉴权查询已在同一 session 中开启事务，直接写入并提交，不再调用 begin()。
    try:
        repository = ConversationRepository(session)
        await repository.lock_creation(user_id)
        conversation = await repository.get_unstarted_by_user(user_id)
        reused = conversation is not None
        if conversation is None:
            conversation = await repository.insert(user_id, title)
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    return conversation, reused


async def list_user_conversations(
    session: AsyncSession, user_id: int, offset: int = 0, limit: int = 20
) -> list[Conversation]:
    return await ConversationRepository(session).list_by_user(user_id, offset, limit)


async def get_user_conversation(
    session: AsyncSession, user_id: int, conversation_id: str
) -> Conversation | None:
    return await ConversationRepository(session).get_owned_by_id(
        conversation_id, user_id
    )
