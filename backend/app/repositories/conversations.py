from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert(self, user_id: int, title: str) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def list_by_user(
        self, user_id: int, offset: int = 0, limit: int = 20
    ) -> list[Conversation]:
        result = await self.session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def get_owned_by_id(
        self, conversation_id: str, user_id: int
    ) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )

    async def try_lock_messages(self, conversation_id: str) -> bool:
        # 事务级 advisory lock 跨进程保护同一个 checkpoint；不锁会话行，
        # 避免与 Save 专用 session 的会话行锁互相等待。commit/rollback 自动释放。
        return bool(
            await self.session.scalar(
                select(
                    func.pg_try_advisory_xact_lock(
                        func.hashtextextended(f"travelbuddy:messages:{conversation_id}", 0)
                    )
                )
            )
        )

    async def touch(self, conversation_id: str, user_id: int) -> None:
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .values(updated_at=func.clock_timestamp())
        )
