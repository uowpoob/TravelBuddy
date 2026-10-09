from uuid import NAMESPACE_URL, uuid5

from langchain_core.messages import HumanMessage

from backend.app.graph.state import TripState


def question_message_id(state: TripState, kind: str) -> str:
    """暂停时展示的问题与恢复后写入的消息使用同一个稳定 ID。"""
    latest = next(
        (
            message
            for message in reversed(state.get("messages", []))
            if isinstance(message, HumanMessage)
        ),
        None,
    )
    source = (latest.id or latest.content) if latest is not None else "initial"
    return str(uuid5(NAMESPACE_URL, f"travelbuddy:question:{kind}:{source}"))
