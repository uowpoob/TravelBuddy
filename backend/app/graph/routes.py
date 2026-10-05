from typing import Literal, cast

from backend.app.graph.state import TripState
from backend.app.schemas.review import ReviewResult


MAX_REVISIONS = 2


def route_after_understand(
    state: TripState,
) -> list[Literal["clarify", "researcher", "context_analyst"]]:
    """信息不足则澄清，完整则同时启动两支调研。"""
    if state["missing_fields"]:
        return ["clarify"]
    return ["researcher", "context_analyst"]


def route_after_review(state: TripState) -> Literal["confirm", "planner", "clarify"]:
    """审核节点负责产出 ReviewResult；主图只决定后续路径。"""
    review = cast(ReviewResult, state["review_result"])
    if review.decision == "pass":
        return "confirm"
    if review.decision == "revise" and state["revision_count"] < MAX_REVISIONS:
        return "planner"
    return "clarify"


def route_after_confirm(state: TripState) -> Literal["save", "understand"]:
    """接受方案则保存，提出修改则重新理解需求。"""
    return "save" if state["confirmed"] else "understand"
