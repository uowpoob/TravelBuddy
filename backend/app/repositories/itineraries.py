from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from backend.app.models import Conversation, SavedItinerary


class ItineraryRepository:
    """行程查询与写入；事务和会话行锁的生命周期由服务层控制。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_user(
        self, user_id: int, offset: int = 0, limit: int = 20
    ) -> list[SavedItinerary]:
        result = await self.session.scalars(
            select(SavedItinerary)
            .join(Conversation, Conversation.id == SavedItinerary.conversation_id)
            .where(Conversation.user_id == user_id)
            .options(
                load_only(
                    SavedItinerary.id,
                    SavedItinerary.conversation_id,
                    SavedItinerary.version,
                    SavedItinerary.title,
                    SavedItinerary.destination_city,
                    SavedItinerary.start_date,
                    SavedItinerary.days,
                    SavedItinerary.created_at,
                )
            )
            .order_by(SavedItinerary.created_at.desc(), SavedItinerary.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def get_owned_by_id(
        self, itinerary_id: int, user_id: int
    ) -> SavedItinerary | None:
        return await self.session.scalar(
            select(SavedItinerary)
            .join(Conversation, Conversation.id == SavedItinerary.conversation_id)
            .where(SavedItinerary.id == itinerary_id, Conversation.user_id == user_id)
        )

    async def lock_owned_conversation(
        self, conversation_id: str, user_id: int
    ) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .with_for_update()
        )

    async def find_saved(
        self, conversation_id: str, save_key: str
    ) -> SavedItinerary | None:
        return await self.session.scalar(
            select(SavedItinerary).where(
                SavedItinerary.conversation_id == conversation_id,
                SavedItinerary.save_key == save_key,
            )
        )

    async def next_version(self, conversation_id: str) -> int:
        # 调用方须已锁定会话行，避免同一会话并发分配相同版本。
        return await self.session.scalar(
            select(func.coalesce(func.max(SavedItinerary.version), 0) + 1).where(
                SavedItinerary.conversation_id == conversation_id
            )
        )

    async def insert_snapshot(
        self,
        *,
        conversation_id: str,
        save_key: str,
        version: int,
        snapshot: dict[str, Any],
        conversation: Conversation,
    ) -> SavedItinerary:
        record = SavedItinerary(
            conversation_id=conversation_id,
            save_key=save_key,
            version=version,
            **snapshot,
        )
        self.session.add(record)
        conversation.updated_at = func.now()
        await self.session.flush()
        return record
