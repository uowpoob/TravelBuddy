import json
from datetime import datetime, timedelta, timezone

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState
from backend.app.prompts.understand import SYSTEM_PROMPT
from backend.app.schemas.place import Candidates
from backend.app.schemas.structured_output import RequestUnderstanding
from backend.app.schemas.trip import (
    REQUIRED_FIELDS,
    TravelConstraints,
    TripRequest,
    missing_request_fields,
)


def missing_fields_question(fields: list[str]) -> str:
    labels = {**REQUIRED_FIELDS, "budget_scope": "预算是全体总额还是人均"}
    return "请补充或确认：" + "、".join(labels[field] for field in fields) + "。"


class UnderstandNode:
    """理解或更新旅行需求。"""

    def __init__(self, model: BaseChatModel | None = None):
        self.model = model

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        current = state.get("trip_request", TripRequest())
        messages = state.get("messages", [])
        latest = next(
            (
                message
                for message in reversed(messages)
                if isinstance(message, HumanMessage)
            ),
            None,
        )
        new_trip = False
        question = None
        last_message_id = state.get("last_understood_message_id")
        if (
            latest is not None
            and latest.id is not None
            and latest.id == last_message_id
        ):
            return {}
        if latest is not None and (latest.id is None or latest.id != last_message_id):
            if self.model is None:
                from backend.app.integrations.llm.deepseek import chat_model

                self.model = chat_model
            review = state.get("review_result")
            payload = {
                "timezone": "Asia/Shanghai",
                "current_date": datetime.now(timezone(timedelta(hours=8)))
                .date()
                .isoformat(),
                "trip_request": current.model_dump(mode="json"),
                "recent_messages": [
                    {"role": message.type, "content": message.content}
                    for message in messages[-12:]
                ],
                "latest_user_message": latest.content,
                "review_result": review.model_dump(mode="json") if review else None,
            }
            extracted = await self.model.with_structured_output(
                RequestUnderstanding
            ).ainvoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ],
                config=config,
            )
            understanding = RequestUnderstanding.model_validate(extracted)
            new_trip = understanding.new_trip
            base = TripRequest() if new_trip else current
            updates = {
                field: getattr(understanding.trip_request, field)
                for field in understanding.updated_fields
            }
            current = TripRequest.model_validate({**base.model_dump(), **updates})
            question = (
                understanding.clarification_question.strip()
                if understanding.clarification_question
                else None
            )
            last_message_id = latest.id

        missing = missing_request_fields(current)
        if missing:
            missing_question = missing_fields_question(missing)
            question = (
                f"{question}\n{missing_question}" if question else missing_question
            )
        return {
            "trip_request": current,
            "missing_fields": missing,
            "clarification_question": question,
            "last_understood_message_id": last_message_id,
            "candidates": Candidates(),
            "travel_constraints": TravelConstraints(),
            "itinerary": None if new_trip else state.get("itinerary"),
            "review_result": None,
            "revision_count": 0,
            "confirmed": False,
            "save_key": None,
            "saved_itinerary_id": None,
            "saved_itinerary_version": None,
        }
