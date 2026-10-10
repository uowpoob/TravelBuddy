from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Conversation, User


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert(self, user_id: int, title: str) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def lock_creation(self, user_id: int) -> None:
        # 锁定用户行，跨进程串行化“检查空会话 + 创建”，避免多标签页重复创建。
        await self.session.execute(
            select(User.id).where(User.id == user_id).with_for_update()
        )

    async def get_unstarted_by_user(self, user_id: int) -> Conversation | None:
        # 首次发送前 progress 为 NULL；发送开始后独立提交 running 状态。
        # 标题由用户自定，不能用默认标题判断是否已经聊天。
        return await self.session.scalar(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                or_(
                    Conversation.planning_progress.is_(None),
                    Conversation.planning_progress["status"].as_string() == "idle",
                ),
            )
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .limit(1)
        )

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
                        func.hashtextextended(
                            f"travelbuddy:messages:{conversation_id}", 0
                        )
                    )
                )
            )
        )

    async def touch(
        self, conversation_id: str, user_id: int, title: str | None = None
    ) -> None:
        values = {"updated_at": func.clock_timestamp()}
        if title is not None:
            values["title"] = title
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .values(**values)
        )

    async def read_progress(
        self, conversation_id: str, user_id: int
    ) -> dict[str, Any] | None:
        return await self.session.scalar(
            select(Conversation.planning_progress).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )

    async def write_progress(
        self, conversation_id: str, user_id: int, progress: dict[str, Any]
    ) -> None:
        result = await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .values(planning_progress=progress, updated_at=Conversation.updated_at)
        )
        if result.rowcount != 1:
            raise ValueError("会话不存在，无法更新规划状态。")
