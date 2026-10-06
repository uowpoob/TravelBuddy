"""Context Analyst 的天气工具选择与加载。"""

from collections.abc import Sequence

from langchain_core.tools import BaseTool

from backend.app.integrations.mcp.adapter import load_amap_tools
from backend.app.integrations.mcp.client import AmapMCPClient, AmapMCPError


CONTEXT_ANALYST_TOOL_NAMES = ("maps_weather",)


def select_context_analyst_tools(tools: Sequence[BaseTool]) -> list[BaseTool]:
    """从内存中的工具列表筛选天气工具；缺少工具时明确报错。"""
    tools_by_name = {tool.name: tool for tool in tools}
    missing = [name for name in CONTEXT_ANALYST_TOOL_NAMES if name not in tools_by_name]
    if missing:
        raise AmapMCPError(f"Context Analyst 缺少高德工具：{', '.join(missing)}")
    return [tools_by_name[name] for name in CONTEXT_ANALYST_TOOL_NAMES]


async def load_context_analyst_tools(client: AmapMCPClient) -> list[BaseTool]:
    """通过 MCP 发现和适配工具，再本地筛选；此时不查询天气。"""
    tools = await load_amap_tools(client)
    return select_context_analyst_tools(tools)
