from datetime import timedelta

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import ConfigDict, Field, RootModel

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.messages import question_message_id
from backend.app.graph.state import TripState
from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.trip import TripRequest

CONFIRMATION_QUESTION = (
    "是否接受当前行程？回复“确认”接受方案；如需修改，请直接说明修改要求。"
)
CONFIRMATION_PHRASES = {
    "确认",
    "确认行程",
    "确认方案",
    "确认保存",
    "确认并保存",
    "同意",
    "接受",
    "可以",
    "好的",
    "好",
    "没问题",
    "就按这个方案",
    "就按这个行程",
    "ok",
    "yes",
}


class ConfirmationAnswer(RootModel[str]):
    """确认或修改使用非空文本，校验失败后可用同一 thread_id 重试。"""

    model_config = ConfigDict(str_strip_whitespace=True)
    root: str = Field(min_length=1)


def format_itinerary(
    itinerary: Itinerary,
    candidates: Candidates,
    request: TripRequest | None,
) -> str:
    """将实际行程和候选地点格式化为确认文本，不补造地点或费用。"""
    places = {
        place.id: place
        for place in (
            candidates.attractions + candidates.restaurants + candidates.hotels
        )
    }
    destination = request.destination_city if request else None
    lines = [f"{destination}行程方案" if destination else "行程方案"]
    if request:
        if request.travelers is not None:
            lines.append(f"出行人数：{request.travelers} 人")
        if request.transport:
            lines.append(f"交通方式：{request.transport}")
        if request.budget is not None:
            scope = {"total": "全体总额", "per_person": "人均"}.get(
                request.budget_scope, "口径未明确"
            )
            lines.append(f"预算（{scope}）：{request.budget:,.2f} 元")

    for day in itinerary.days:
        title = f"第 {day.day} 天"
        if request and request.start_date:
            day_date = request.start_date + timedelta(days=day.day - 1)
            title += f"（{day_date.isoformat()}）"
        lines.extend(["", title])
        if not day.visits:
            lines.append("暂无具体活动安排。")
        for index, visit in enumerate(day.visits, start=1):
            place = places.get(visit.place_id)
            name = place.name if place else f"地点 ID：{visit.place_id}（名称未提供）"
            if place and place.address:
                name += f"（{place.address}）"
            details = [f"{index}. {name}", f"预计停留 {visit.stay_minutes} 分钟"]
            if visit.transport or visit.travel_minutes is not None:
                transport = visit.transport or "交通方式未提供"
                duration = (
                    f"约 {visit.travel_minutes} 分钟"
                    if visit.travel_minutes is not None
                    else "耗时未知"
                )
                details.append(f"到达交通：{transport}，{duration}")
            lines.append("；".join(details))

    cost = itinerary.estimated_cost
    lines.extend(["", "预计费用（全体出行人员，人民币）"])
    lines.append(
        f"总额：{cost.total:,.2f} 元" if cost.total is not None else "总额：尚未估算"
    )
    lines.extend(f"- {item}：{amount:,.2f} 元" for item, amount in cost.breakdown.items())
    if itinerary.notes:
        lines.extend(["", "行程说明"])
        lines.extend(f"- {note}" for note in itinerary.notes)
    return "\n".join(lines)


class ConfirmNode:
    """等待用户确认方案或提出修改要求。"""

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """展示行程并暂停，回答写入 messages，既有条件边决定后续路径。"""
        itinerary = state.get("itinerary")
        if itinerary is None or not itinerary.days:
            raise ValueError("没有可确认的行程，不能进入 Confirm。")
        request = state.get("trip_request")
        candidates = state.get("candidates", Candidates())
        summary = format_itinerary(itinerary, candidates, request)
        payload = {
            "type": "confirm",
            "question": CONFIRMATION_QUESTION,
            "summary": summary,
            "trip_request": request.model_dump(mode="json") if request else None,
            "itinerary": itinerary.model_dump(mode="json"),
            "candidates": candidates.model_dump(mode="json"),
        }
        answer = interrupt(payload, response_schema=ConfirmationAnswer)

        # 仅完整匹配确认用语，包含修改要求的回答必须交回 Understand。
        normalized = answer.root.casefold().rstrip("。.!！").strip()
        confirmed = normalized in CONFIRMATION_PHRASES
        # 中断前只读取状态；取得有效回答后才追加消息，保留方案作为修改上下文。
        return {
            "messages": [
                AIMessage(
                    content=f"{summary}\n\n{CONFIRMATION_QUESTION}",
                    id=question_message_id(state, "confirm"),
                ),
                HumanMessage(content=answer.root),
            ],
            "confirmed": confirmed,
        }
