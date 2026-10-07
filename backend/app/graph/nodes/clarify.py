from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import ConfigDict, Field, RootModel

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.understand import missing_fields_question
from backend.app.graph.state import TripState


class ClarificationAnswer(RootModel[str]):
    """Command(resume=...) 接收非空文本，校验失败后可用同一 thread_id 重试。"""

    model_config = ConfigDict(str_strip_whitespace=True)
    root: str = Field(min_length=1)


class ClarifyNode:
    """等待用户补充信息或对冲突条件作出选择。"""

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """暂停后接收非空文字回答，由既有条件边返回 Understand。"""
        review = state.get("review_result")
        missing = state.get("missing_fields", [])
        question = (state.get("clarification_question") or "").strip()
        if not question and review:
            question = (review.clarification_question or "").strip()
        if not question and missing:
            question = missing_fields_question(missing)
        if not question and review and review.issues:
            question = "当前行程存在以下问题：\n" + "\n".join(review.issues)
            question += "\n请说明希望调整哪些条件或如何取舍。"
        if not question:
            question = "当前行程暂时无法满足要求，请说明希望调整哪些条件或如何取舍。"

        payload = {
            "type": "clarify",
            "question": question,
            "missing_fields": missing,
            "issues": review.issues if review else [],
        }
        answer = interrupt(payload, response_schema=ClarificationAnswer)

        # 恢复会重跑 interrupt 前的代码，消息只在取得有效回答后写入。
        # 将问题也保留在对话中，Understand 才能理解“人均”等简短回答。
        return {
            "messages": [
                AIMessage(content=question),
                HumanMessage(content=answer.root),
            ]
        }
