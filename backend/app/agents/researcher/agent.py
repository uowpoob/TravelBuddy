from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from backend.app.prompts.researcher import SYSTEM_PROMPT
from backend.app.schemas.place import Candidates


def build_researcher_agent(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """创建地点调研 Agent；查询工具暂未接入。"""
    from backend.app.integrations.llm.deepseek import chat_model

    return create_agent(
        model=chat_model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Candidates),
        checkpointer=checkpointer,
    )
