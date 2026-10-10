from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.core.planning import PLANNING_NODES

PlanningStatus = Literal[
    "idle",
    "running",
    "waiting_clarification",
    "waiting_approval",
    "completed",
    "failed",
]
NodeStatus = Literal["pending", "running", "completed", "failed", "waiting"]


class PlanningProgressState(BaseModel):
    """One current-state document, overwritten during each message turn."""

    status: PlanningStatus = "idle"
    nodes: dict[str, NodeStatus] = Field(
        default_factory=lambda: {name: "pending" for name in PLANNING_NODES}
    )
    error: str | None = None

    def finish(self, status: PlanningStatus, error: str | None = None) -> None:
        self.status = status
        self.error = error
        waiting_node = (
            "clarify"
            if status == "waiting_clarification"
            else "confirm"
            if status == "waiting_approval"
            else None
        )
        for name, node_status in self.nodes.items():
            if node_status == "running":
                self.nodes[name] = "waiting" if name == waiting_node else "failed"
        if waiting_node is not None:
            self.nodes[waiting_node] = "waiting"


class PlanningProgressOut(PlanningProgressState):
    conversation_id: UUID
