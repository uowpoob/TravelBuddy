"""统一发现和适配工具，再按角色创建四个专业 Agent。"""

from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.context_analyst.agent import build_context_analyst_agent
from backend.app.agents.planner.agent import build_planner_agent
from backend.app.agents.researcher.agent import build_researcher_agent
from backend.app.agents.reviewer.agent import build_reviewer_agent
from backend.app.integrations.mcp.adapter import load_amap_tools
from backend.app.integrations.mcp.client import AmapMCPClient


async def build_agents(client: AmapMCPClient) -> dict[str, CompiledStateGraph]:
    """一次工具发现流程，共享结果并由各工厂本地筛选。

    FastAPI 生命周期在配置完整时调用，保存 Agent 并将其注入总图的专业子节点。
    创建 Agent 不执行模型或业务工具。
    """
    all_tools = await load_amap_tools(client)

    return {
        "researcher": build_researcher_agent(tools=all_tools),
        "context_analyst": build_context_analyst_agent(tools=all_tools),
        "planner": build_planner_agent(tools=all_tools),
        "reviewer": build_reviewer_agent(),
    }
