from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from backend.app.prompts.reviewer import SYSTEM_PROMPT
from backend.app.schemas.structured_output import ReviewResult


def build_reviewer_agent(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """创建方案审核 Agent；只读取输入，不依赖数据库或业务工具。"""
    from backend.app.integrations.llm.deepseek import chat_model

    return create_agent(
        model=chat_model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(ReviewResult),
        checkpointer=checkpointer,
    )
