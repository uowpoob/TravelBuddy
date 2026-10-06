"""Planner 的路线与距离工具选择和加载；预算工具后续实现。"""

from collections.abc import Sequence

from langchain_core.tools import BaseTool

from backend.app.integrations.mcp.adapter import load_amap_tools
from backend.app.integrations.mcp.client import AmapMCPClient, AmapMCPError


PLANNER_TOOL_NAMES = (
    "maps_direction_walking",
    "maps_direction_driving",
    "maps_direction_bicycling",
    "maps_direction_transit_integrated",
    "maps_distance",
)


def select_planner_tools(tools: Sequence[BaseTool]) -> list[BaseTool]:
    """从内存中的工具列表筛选路线工具；缺少必要工具时明确报错。"""
    tools_by_name = {tool.name: tool for tool in tools}
    missing = [name for name in PLANNER_TOOL_NAMES if name not in tools_by_name]
    if missing:
        raise AmapMCPError(f"Planner 缺少高德工具：{', '.join(missing)}")
    return [tools_by_name[name] for name in PLANNER_TOOL_NAMES]


async def load_planner_tools(client: AmapMCPClient) -> list[BaseTool]:
    """通过 MCP 发现和适配工具，再本地筛选；此时不查询实际路线。"""
    tools = await load_amap_tools(client)
    return select_planner_tools(tools)
