from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.context_analyst.tools import select_context_analyst_tools
from backend.app.prompts.context_analyst import SYSTEM_PROMPT
from backend.app.schemas.trip import TravelConstraints


def build_context_analyst_agent(
    *,
    tools: Sequence[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """绑定天气工具，创建输出 TravelConstraints 的出行约束 Agent。

    调用方先异步加载工具，再显式传入；构建本身不访问高德或执行模型。
    """
    context_tools = select_context_analyst_tools(tools)
    from backend.app.integrations.llm.deepseek import chat_model

    return create_agent(
        model=chat_model,
        tools=context_tools,
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(TravelConstraints),
        checkpointer=checkpointer,
    )
