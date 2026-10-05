from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from backend.app.prompts.context_analyst import SYSTEM_PROMPT
from backend.app.schemas.trip import TravelConstraints


def build_context_analyst_agent(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """创建出行约束 Agent；工具暂未接入，不依赖数据库。"""
    from backend.app.integrations.llm.deepseek import chat_model

    return create_agent(
        model=chat_model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(TravelConstraints),
        checkpointer=checkpointer,
    )
