from typing import Literal

from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    """Reviewer 的结构化输出，同时保存在 TripState.review_result。"""

    decision: Literal["pass", "revise", "needs_user"]
    issues: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
