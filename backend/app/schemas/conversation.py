from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.trip import TripRequest


class ConversationCreate(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ] = "新旅行"


class ConversationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationCreated(ConversationPublic):
    reused: bool = False


class MessageCreate(BaseModel):
    content: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=10000),
        ]
        | None
    ) = None
    retry: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def validate_input(self) -> "MessageCreate":
        if self.retry == (self.content is not None):
            raise ValueError("请发送 content，或使用 retry=true 重试未完成的步骤。")
        return self


class ChatMessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str


class ConversationInterruptOut(BaseModel):
    type: Literal["clarify", "confirm"]
    question: str
    summary: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    trip_request: TripRequest | None = None
    itinerary: Itinerary | None = None
    candidates: Candidates | None = None


class ConversationStateOut(BaseModel):
    conversation_id: UUID
    title: str | None = None
    status: Literal["completed", "waiting_clarification", "waiting_approval", "pending"]
    interrupt: ConversationInterruptOut | None = None
    saved_itinerary_id: int | None = None
    saved_itinerary_version: int | None = None


class ConversationMessagesOut(ConversationStateOut):
    items: list[ChatMessageOut]
    total: int
    offset: int
    limit: int


class MessageTurnOut(ConversationStateOut):
    items: list[ChatMessageOut]
