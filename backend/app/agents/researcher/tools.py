"""Researcher 的地点查询工具选择与加载。"""

from collections.abc import Sequence

from langchain_core.tools import BaseTool

from backend.app.integrations.mcp.adapter import load_amap_tools
from backend.app.integrations.mcp.client import AmapMCPClient, AmapMCPError


RESEARCHER_TOOL_NAMES = (
    "maps_text_search",
    "maps_around_search",
    "maps_search_detail",
    "maps_geo",
)


def select_researcher_tools(tools: Sequence[BaseTool]) -> list[BaseTool]:
    """按角色筛选已适配工具；缺少必要工具时明确报错。"""
    tools_by_name = {tool.name: tool for tool in tools}
    missing = [name for name in RESEARCHER_TOOL_NAMES if name not in tools_by_name]
    if missing:
        raise AmapMCPError(f"Researcher 缺少高德工具：{', '.join(missing)}")
    return [tools_by_name[name] for name in RESEARCHER_TOOL_NAMES]


async def load_researcher_tools(client: AmapMCPClient) -> list[BaseTool]:
    """发现、适配并筛选地点工具；此时不执行业务查询。"""
    tools = await load_amap_tools(client)
    return select_researcher_tools(tools)
