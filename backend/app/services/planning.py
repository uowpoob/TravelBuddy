import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from langchain_core.callbacks import AsyncCallbackHandler
from langgraph.errors import GraphInterrupt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.repositories.conversations import ConversationRepository
from backend.app.schemas.planning import PlanningProgressState, PlanningStatus

logger = logging.getLogger(__name__)


class PlanningProgressRecorder(AsyncCallbackHandler):
    """Update the conversation's node states, without event history."""

    run_inline = True
    raise_error = True

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        conversation_id: str,
        user_id: int,
        node_names: frozenset[str],
    ):
        self.session_factory = session_factory
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.node_names = node_names
        self.root_id = uuid4()
        self.state = PlanningProgressState(status="running")
        self.executions: dict[UUID, str] = {}
        self.lock = asyncio.Lock()
        self.closed = False

    async def _save(self) -> None:
        # Commit separately so GET sees changes while POST still awaits the graph.
        async with self.session_factory() as session, session.begin():
            await ConversationRepository(session).write_progress(
                self.conversation_id, self.user_id, self.state.model_dump(mode="json")
            )

    async def start(self) -> None:
        await self._save()

    async def finish(self, status: PlanningStatus, error: str | None = None) -> None:
        async with self.lock:
            if self.closed:
                return
            self.state.finish(status, error)
            await self._save()
            self.closed = True

    async def fail_safely(self, error: str) -> None:
        try:
            async with asyncio.timeout(10):
                await self.finish("failed", error)
        except Exception as exc:  # noqa: BLE001 -- preserve the original message error
            logger.error("规划失败状态保存失败（%s）。", type(exc).__name__)

    async def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        if parent_run_id != self.root_id or name not in self.node_names:
            return
        async with self.lock:
            if self.closed:
                return
            self.executions[run_id] = name
            self.state.nodes[name] = "running"
            await self._save()

    async def _ended(self, run_id: UUID, *, failed: bool = False) -> None:
        async with self.lock:
            name = self.executions.pop(run_id, None)
            if self.closed or name is None:
                return
            self.state.nodes[name] = "failed" if failed else "completed"
            await self._save()

    async def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        await self._ended(run_id)

    async def on_chain_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        if not isinstance(error, GraphInterrupt):
            await self._ended(run_id, failed=True)
