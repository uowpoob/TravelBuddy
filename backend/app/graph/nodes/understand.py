import json
import logging
from datetime import datetime, timedelta, timezone

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from pydantic import ValidationError

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

logger = logging.getLogger(__name__)


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
        previous = current
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
        refresh_candidates = False
        refresh_weather = False
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
            itinerary = state.get("itinerary")
            candidates = state.get("candidates")
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
                "itinerary": itinerary.model_dump(mode="json") if itinerary else None,
                "candidates": candidates.model_dump(mode="json")
                if candidates
                else None,
                "output_schema": RequestUnderstanding.model_json_schema(),
            }
            # 此节点只提取数据，使用 JSON 输出避免强制工具调用及无效函数参数。
            extractor = self.model.with_structured_output(
                RequestUnderstanding, method="json_mode"
            )
            prompt = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ]
            for attempt in range(2):
                try:
                    extracted = await extractor.ainvoke(prompt, config=config)
                    understanding = RequestUnderstanding.model_validate(extracted)
                    break
                except (OutputParserException, ValidationError) as exc:
                    if attempt == 1:
                        raise
                    logger.warning(
                        "需求输出校验失败，重试一次（%s）。", type(exc).__name__
                    )
            new_trip = understanding.new_trip
            refresh_candidates = understanding.refresh_candidates
            refresh_weather = understanding.refresh_weather
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
        changed_fields = [
            field
            for field in TripRequest.model_fields
            if getattr(previous, field) != getattr(current, field)
        ]
        reset = new_trip or previous.destination_city != current.destination_city
        candidates = Candidates() if reset else state.get("candidates", Candidates())
        constraints = (
            TravelConstraints()
            if reset
            else state.get("travel_constraints", TravelConstraints())
        )
        research_required = (
            reset
            or state.get("research_required", False)
            or not (
                candidates.attractions or candidates.restaurants or candidates.hotels
            )
            or refresh_candidates
            or "preferences" in changed_fields
            or bool(set(current.must_visit) - set(previous.must_visit))
            or (current.days or 0) > (previous.days or 0)
        )
        context_required = (
            reset
            or state.get("context_required", False)
            or "travel_constraints" not in state
            or refresh_weather
            or bool(set(changed_fields) & {"start_date", "days"})
        )
        if changed_fields and not context_required:
            # 天气仍可参考；旧需求摘要可能含旧人数、预算或限制，不继续传给 Planner。
            constraints = constraints.model_copy(
                update={"constraints": [], "suggestions": []}
            )
        itinerary = None if reset else state.get("itinerary")
        return {
            "changed_fields": changed_fields,
            "revision_request": str(latest.content) if latest is not None else None,
            "research_required": research_required,
            "context_required": context_required,
            "candidates": candidates,
            "travel_constraints": constraints,
            "itinerary": itinerary,
            "itinerary_request": (
                state.get("itinerary_request") or previous
                if itinerary is not None
                else None
            ),
            "trip_request": current,
            "missing_fields": missing,
            "clarification_question": question,
            "last_understood_message_id": last_message_id,
            "review_result": None,
            "revision_count": 0,
            "confirmed": False,
            "save_key": None,
            "saved_itinerary_id": None,
            "saved_itinerary_version": None,
        }
