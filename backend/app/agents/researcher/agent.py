from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.researcher.tools import select_researcher_tools
from backend.app.prompts.researcher import SYSTEM_PROMPT
from backend.app.schemas.place import Candidates


def build_researcher_agent(
    *,
    tools: Sequence[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """绑定地点查询工具，创建输出 Candidates 的地点调研 Agent。

    tools 由统一组装入口加载并传入，这里仅本地筛选，不访问高德。
    """
    researcher_tools = select_researcher_tools(tools)
    from backend.app.integrations.llm.deepseek import chat_model

    return create_agent(
        model=chat_model,
        tools=researcher_tools,
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Candidates),
        checkpointer=checkpointer,
    )
