from typing import Literal

from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    """Reviewer 的结构化输出，同时保存在 TripState.review_result。

    宽松审核仍有实际通过、修订和用户取舍判断；通过后方案由用户最终确认。
    """

    decision: Literal["pass", "revise", "needs_user"]
    issues: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
