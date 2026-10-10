import asyncio
import logging
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, StateSnapshot
from openai import APIStatusError
from psycopg import Error as PsycopgError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.graph.context import TravelBuddyContext
from backend.app.repositories.conversations import ConversationRepository
from backend.app.schemas.conversation import (
    ChatMessageOut,
    ConversationInterruptOut,
    ConversationMessagesOut,
    ConversationStateOut,
    MessageCreate,
    MessageTurnOut,
)
from backend.app.schemas.planning import PlanningProgressOut, PlanningProgressState
from backend.app.services.planning import PlanningProgressRecorder

logger = logging.getLogger(__name__)


class ConversationError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def public_state(snapshot: StateSnapshot, conversation_id: str) -> ConversationStateOut:
    interruption = (
        ConversationInterruptOut.model_validate(snapshot.interrupts[0].value)
        if snapshot.interrupts
        else None
    )
    if interruption is not None:
        status = (
            "waiting_clarification"
            if interruption.type == "clarify"
            else "waiting_approval"
        )
    else:
        status = "pending" if snapshot.next else "completed"
    return ConversationStateOut(
        conversation_id=conversation_id,
        title=snapshot.values.get("conversation_title"),
        status=status,
        interrupt=interruption,
        saved_itinerary_id=snapshot.values.get("saved_itinerary_id"),
        saved_itinerary_version=snapshot.values.get("saved_itinerary_version"),
    )


def public_messages(
    snapshot: StateSnapshot, state: ConversationStateOut
) -> list[ChatMessageOut]:
    messages = []
    for index, message in enumerate(snapshot.values.get("messages", [])):
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage) and not message.tool_calls:
            role = "assistant"
        else:
            continue
        content = str(message.text)
        if content.strip():
            messages.append(
                ChatMessageOut(
                    id=message.id or f"{state.conversation_id}:message:{index}",
                    role=role,
                    content=content,
                )
            )
    # 等待回答时仅由 interrupt 面板展示问题，不投影成聊天消息。
    # Clarify/Confirm 恢复后写入的正式问题仍作为历史消息返回。
    return messages


class ConversationChatService:
    def __init__(
        self,
        graph: CompiledStateGraph | None,
        session_factory: async_sessionmaker[AsyncSession] | None,
        *,
        timeout: float = 300,
    ):
        self.graph = graph
        self.session_factory = session_factory
        self.timeout = timeout

    @staticmethod
    def prepare_turn(
        before: StateSnapshot, payload: MessageCreate
    ) -> dict | Command | None:
        if payload.retry:
            if before.interrupts or not before.next:
                raise ConversationError(409, "当前没有可重试的步骤，请发送新的消息。")
            return None
        if before.interrupts:
            return Command(resume=payload.content)
        if before.next:
            raise ConversationError(409, "上轮执行尚未完成，请使用 retry=true 重试。")
        return {"messages": [HumanMessage(content=payload.content, id=str(uuid4()))]}

    async def get_progress(
        self, session: AsyncSession, user_id: int, conversation_id: str
    ) -> PlanningProgressOut:
        repository = ConversationRepository(session)
        conversation = await repository.get_owned_by_id(conversation_id, user_id)
        if conversation is None:
            raise ConversationError(404, "会话不存在。")
        state = PlanningProgressState.model_validate(
            conversation.planning_progress or {}
        )
        if state.status == "running" and await repository.try_lock_messages(
            conversation_id
        ):
            # With no execution lock owner, the old request has stopped. Read
            # again under the lock: it may have finished after our first SELECT.
            try:
                state = PlanningProgressState.model_validate(
                    await repository.read_progress(conversation_id, user_id) or {}
                )
                if state.status == "running":
                    state.finish("failed", "本轮执行已中断，请查看会话状态后继续规划。")
                    await repository.write_progress(
                        conversation_id, user_id, state.model_dump(mode="json")
                    )
                    await session.commit()
            finally:
                if session.in_transaction():
                    await session.rollback()
        return PlanningProgressOut(
            conversation_id=conversation_id, **state.model_dump()
        )

    async def _owned_graph(
        self, session: AsyncSession, user_id: int, conversation_id: str
    ) -> CompiledStateGraph:
        if (
            await ConversationRepository(session).get_owned_by_id(
                conversation_id, user_id
            )
            is None
        ):
            raise ConversationError(404, "会话不存在。")
        if self.graph is None:
            raise ConversationError(503, "旅行流程未就绪，请稍后重试。")
        return self.graph

    @staticmethod
    def _execution_error(exc: Exception) -> ConversationError:
        # 模型、MCP 和 checkpoint 异常可能包含配置秘密或原始输入。
        if isinstance(exc, APIStatusError):
            # 只记录状态码，不输出请求、鉴权信息或上游响应正文。
            logger.error(
                "消息流程执行失败（%s，上游 HTTP %s）。",
                type(exc).__name__,
                exc.status_code,
            )
            if exc.status_code == 402:
                return ConversationError(
                    502,
                    "模型服务余额不足，暂时无法继续规划；处理模型账户余额后可重试本轮。",
                )
        else:
            logger.error("消息流程执行失败（%s）。", type(exc).__name__)
        if isinstance(exc, TimeoutError):
            return ConversationError(504, "本轮执行超时，请查看消息状态后重试。")
        if isinstance(exc, PsycopgError):
            return ConversationError(503, "消息存储暂时不可用，请稍后重试。")
        if isinstance(exc, GraphRecursionError):
            return ConversationError(
                502, "本轮执行达到步数上限，请查看消息状态后重试。"
            )
        return ConversationError(502, "本轮执行失败，请查看消息状态后重试。")

    async def list_messages(
        self,
        session: AsyncSession,
        user_id: int,
        conversation_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> ConversationMessagesOut:
        graph = await self._owned_graph(session, user_id, conversation_id)
        try:
            async with asyncio.timeout(self.timeout):
                snapshot = await graph.aget_state(
                    {"configurable": {"thread_id": conversation_id}}
                )
                state = public_state(snapshot, conversation_id)
                messages = public_messages(snapshot, state)
        except SQLAlchemyError:
            raise
        except Exception as exc:  # noqa: BLE001 -- sanitized graph/API boundary
            raise self._execution_error(exc) from None
        return ConversationMessagesOut(
            **state.model_dump(),
            items=messages[offset : offset + limit],
            total=len(messages),
            offset=offset,
            limit=limit,
        )

    async def send_message(
        self,
        session: AsyncSession,
        user_id: int,
        conversation_id: str,
        payload: MessageCreate,
    ) -> MessageTurnOut:
        graph = await self._owned_graph(session, user_id, conversation_id)
        if self.session_factory is None:
            raise ConversationError(503, "数据库暂时不可用，请稍后重试。")
        repository = ConversationRepository(session)
        config = {
            "configurable": {"thread_id": conversation_id},
            "recursion_limit": 50,
        }
        progress: PlanningProgressRecorder | None = None
        try:
            if not await repository.try_lock_messages(conversation_id):
                raise ConversationError(409, "该会话正在处理消息，请稍后重试。")
            async with asyncio.timeout(self.timeout):
                before = await graph.aget_state(config)
                before_state = public_state(before, conversation_id)
                previous_ids = {
                    message.id for message in public_messages(before, before_state)
                }
                graph_input = self.prepare_turn(before, payload)
                progress = PlanningProgressRecorder(
                    self.session_factory,
                    conversation_id,
                    user_id,
                    frozenset(
                        name for name in graph.nodes if not name.startswith("__")
                    ),
                )
                await progress.start()
                execution_config = {
                    **config,
                    "run_id": progress.root_id,
                    "callbacks": [progress],
                }
                # Save 自己开启事务；不得复用鉴权/归属查询已经开启的事务。
                async with self.session_factory() as save_session:
                    await graph.ainvoke(
                        graph_input,
                        config=execution_config,
                        context=TravelBuddyContext(
                            user_id=user_id,
                            conversation_id=conversation_id,
                            db=save_session,
                        ),
                        durability="sync",
                    )
                after = await graph.aget_state(config)
                state = public_state(after, conversation_id)
                if state.status == "pending":
                    await progress.finish(
                        "failed",
                        "本轮已停止，但还有未完成步骤，请查看会话状态后重试。",
                    )
                else:
                    await progress.finish(state.status)
                items = [
                    message
                    for message in public_messages(after, state)
                    if message.id not in previous_ids
                ]
            await repository.touch(conversation_id, user_id, state.title)
            await session.commit()
            return MessageTurnOut(**state.model_dump(), items=items)
        except asyncio.CancelledError:
            if progress is not None:
                await progress.fail_safely("本轮执行已取消，请查看会话状态后继续规划。")
            raise
        except ConversationError as exc:
            if progress is not None:
                await progress.fail_safely(exc.message)
            raise
        except SQLAlchemyError:
            if progress is not None:
                await progress.fail_safely(
                    "规划进度存储暂时不可用，请查看会话状态后重试。"
                )
            raise
        except Exception as exc:  # noqa: BLE001 -- sanitized graph/API boundary
            error = self._execution_error(exc)
            if progress is not None:
                await progress.fail_safely(error.message)
            raise error from None
        finally:
            # 异常和请求取消时也释放事务级锁，checkpoint 保留可恢复的进度。
            if session.in_transaction():
                await session.rollback()
