from typing import Literal

from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    decision: Literal["pass", "revise", "needs_user"]
    issues: list[str] = Field(default_factory=list)
