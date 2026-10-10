import asyncio

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Conversation, SavedItinerary
from backend.app.repositories.conversations import ConversationRepository
from backend.app.repositories.itineraries import ItineraryRepository
from backend.app.schemas.deletion import DeletionImpact
from backend.app.services.messages import ConversationError


async def conversation_deletion_impact(
    session: AsyncSession, user_id: int, conversation_id: str
) -> DeletionImpact:
    conversation = await ConversationRepository(session).get_owned_by_id(
        conversation_id, user_id
    )
    if conversation is None:
        raise ConversationError(404, "会话不存在。")
    count = await session.scalar(
        select(func.count())
        .select_from(SavedItinerary)
        .where(SavedItinerary.conversation_id == conversation_id)
    )
    related = f"，以及关联的 {count} 份已保存行程（含各个版本）" if count else ""
    return DeletionImpact(
        title=conversation.title,
        message=f"删除后，这个会话和全部聊天记录{related}将永久删除，无法恢复。",
        related_itinerary_count=count,
    )


async def itinerary_deletion_impact(
    session: AsyncSession, user_id: int, itinerary_id: int
) -> DeletionImpact:
    itinerary = await ItineraryRepository(session).get_owned_by_id(
        itinerary_id, user_id
    )
    if itinerary is None:
        raise ConversationError(404, "行程不存在。")
    return DeletionImpact(
        title=itinerary.title,
        message=(
            f"删除后，第 {itinerary.version} 版行程将无法再查看或在地图上展示，无法恢复。"
            "关联会话、聊天记录和其他行程版本会保留，你可以继续在会话中规划。"
        ),
    )


async def lock_conversation(
    session: AsyncSession, user_id: int, conversation_id: str
) -> None:
    repository = ConversationRepository(session)
    if await repository.get_owned_by_id(conversation_id, user_id) is None:
        raise ConversationError(404, "会话不存在。")
    # 与消息发送使用同一把锁，避免删除期间仍在规划或保存行程。
    if not await repository.try_lock_messages(conversation_id):
        raise ConversationError(409, "该会话正在处理消息，请等本轮结束后再删除。")
    if (
        await ItineraryRepository(session).lock_owned_conversation(
            conversation_id, user_id
        )
        is None
    ):
        raise ConversationError(404, "会话不存在。")


async def delete_conversation(
    session: AsyncSession,
    user_id: int,
    conversation_id: str,
    graph: CompiledStateGraph | None,
    *,
    confirmed: bool,
    delete_itineraries: bool,
    expected_itinerary_count: int,
) -> None:
    try:
        await lock_conversation(session, user_id, conversation_id)
        impact = await conversation_deletion_impact(session, user_id, conversation_id)
        if not confirmed:
            raise ConversationError(409, impact.message + "请先确认是否删除。")
        if impact.related_itinerary_count != expected_itinerary_count:
            raise ConversationError(
                409, "关联行程数量已变化，请重新查看删除影响并确认。"
            )
        if impact.related_itinerary_count and not delete_itineraries:
            raise ConversationError(
                409, impact.message + "请确认是否一并删除关联行程。"
            )
        if graph is None or graph.checkpointer is None:
            raise ConversationError(503, "聊天存储暂时不可用，请稍后再删除会话。")
        # 显式确认后才处理外键依赖，不修改数据库的 RESTRICT 约束。
        if delete_itineraries:
            await session.execute(
                delete(SavedItinerary).where(
                    SavedItinerary.conversation_id == conversation_id
                )
            )
        await session.execute(
            delete(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
        try:
            async with asyncio.timeout(15):
                await graph.checkpointer.adelete_thread(conversation_id)
        except Exception as exc:
            raise ConversationError(503, "聊天记录清理失败，请稍后重试。") from exc
        await session.commit()
    finally:
        if session.in_transaction():
            await session.rollback()


async def delete_itinerary(
    session: AsyncSession, user_id: int, itinerary_id: int, *, confirmed: bool
) -> None:
    try:
        itinerary = await ItineraryRepository(session).get_owned_by_id(
            itinerary_id, user_id
        )
        if itinerary is None:
            raise ConversationError(404, "行程不存在。")
        await lock_conversation(session, user_id, itinerary.conversation_id)
        # 加锁后重新查询：另一请求可能已删除这份行程。
        impact = await itinerary_deletion_impact(session, user_id, itinerary_id)
        if not confirmed:
            raise ConversationError(409, impact.message + "请先确认是否删除。")
        await session.execute(
            delete(SavedItinerary).where(SavedItinerary.id == itinerary_id)
        )
        await session.commit()
    finally:
        if session.in_transaction():
            await session.rollback()
