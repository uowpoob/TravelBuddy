from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.planner.tools import select_planner_tools
from backend.app.prompts.planner import SYSTEM_PROMPT
from backend.app.schemas.itinerary import Itinerary


def build_planner_agent(
    *,
    tools: Sequence[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """绑定路线工具，创建输出 Itinerary 的行程规划 Agent。

    tools 由统一组装入口加载并传入，这里仅本地筛选；预算工具尚未实现。
    构建本身不访问高德或执行模型。
    """
    planner_tools = select_planner_tools(tools)
    from backend.app.integrations.llm.deepseek import chat_model

    return create_agent(
        model=chat_model,
        tools=planner_tools,
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Itinerary),
        checkpointer=checkpointer,
    )
