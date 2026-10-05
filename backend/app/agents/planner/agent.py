from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from backend.app.prompts.planner import SYSTEM_PROMPT
from backend.app.schemas.itinerary import Itinerary


def build_planner_agent(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """创建行程规划 Agent；路线和预算工具暂未接入。"""
    from backend.app.integrations.llm.deepseek import chat_model

    return create_agent(
        model=chat_model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Itinerary),
        checkpointer=checkpointer,
    )
