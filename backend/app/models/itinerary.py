from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SavedItinerary(Base):
    """用户确认的行程版本快照；修改后另存版本，不覆盖旧行程。

    trip_request / itinerary / candidates 保存业务模型的 JSON 数据。
    candidates 保留 place_id 对应的名称、地址和坐标，供独立展示行程。
    save_key 在 Planner 完成时写入 State，保存重试时保持不变。
    version 在 Save 的事务中按会话递增分配，不使用 State.revision_count。
    用户归属通过 conversation_id -> conversations.user_id 获取。
    """

    __tablename__ = "itineraries"
    __table_args__ = (
        UniqueConstraint("conversation_id", "version"),
        UniqueConstraint("conversation_id", "save_key"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("days BETWEEN 1 AND 5", name="days_range"),
        CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
        CheckConstraint(
            "length(btrim(destination_city)) > 0", name="destination_city_not_blank"
        ),
        CheckConstraint(
            "jsonb_typeof(trip_request) = 'object'", name="trip_request_object"
        ),
        CheckConstraint("jsonb_typeof(itinerary) = 'object'", name="itinerary_object"),
        CheckConstraint(
            "jsonb_typeof(candidates) = 'object'", name="candidates_object"
        ),
        CheckConstraint(
            "travel_constraints IS NULL OR jsonb_typeof(travel_constraints) = 'object'",
            name="travel_constraints_object",
        ),
        CheckConstraint(
            "review_result IS NULL OR jsonb_typeof(review_result) = 'object'",
            name="review_result_object",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="RESTRICT")
    )
    save_key: Mapped[str] = mapped_column(
        UUID(as_uuid=False), server_default=func.gen_random_uuid()
    )
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    destination_city: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer)
    trip_request: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True))
    itinerary: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True))
    candidates: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True))
    travel_constraints: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True)
    )
    review_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
