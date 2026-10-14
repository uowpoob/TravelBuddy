"""Planner 从统一加载的工具列表中选择路线与距离工具。"""

from collections.abc import Sequence

from langchain_core.tools import BaseTool

from backend.app.integrations.mcp.client import AmapMCPError

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
