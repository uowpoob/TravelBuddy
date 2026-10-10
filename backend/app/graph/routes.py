from typing import Literal

from backend.app.graph.state import TripState

MAX_REVISIONS = 1


def route_after_understand(
    state: TripState,
) -> list[Literal["clarify", "researcher", "context_analyst"]]:
    """信息不足则澄清；完整时两支调研按失效标记执行或直接复用。"""
    if state["missing_fields"] or state.get("clarification_question"):
        return ["clarify"]
    return ["researcher", "context_analyst"]


def route_after_review(state: TripState) -> Literal["confirm", "planner", "clarify"]:
    """通过才确认；可修复问题有限修订；真实取舍及修订未解决的问题进入澄清。"""
    review = state.get("review_result")
    if review is None:
        raise ValueError("尚未产生审核结果，不能进入确认。")
    if review.decision == "pass":
        return "confirm"
    if review.decision == "revise" and state.get("revision_count", 0) < MAX_REVISIONS:
        return "planner"
    return "clarify"


def route_after_confirm(state: TripState) -> Literal["save", "understand"]:
    """接受方案则保存，提出修改则重新理解需求。"""
    return "save" if state["confirmed"] else "understand"
