from collections.abc import Mapping

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.context_analyst.graph import build_context_analyst_graph
from backend.app.agents.planner.graph import build_planner_graph
from backend.app.agents.researcher.graph import build_researcher_graph
from backend.app.agents.reviewer.graph import build_reviewer_graph
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.clarify import ClarifyNode
from backend.app.graph.nodes.confirm import ConfirmNode
from backend.app.graph.nodes.context_analyst import ContextAnalystNode
from backend.app.graph.nodes.planner import PlannerNode
from backend.app.graph.nodes.researcher import ResearcherNode
from backend.app.graph.nodes.reviewer import ReviewerNode
from backend.app.graph.nodes.save import SaveNode
from backend.app.graph.nodes.understand import UnderstandNode
from backend.app.graph.routes import (
    route_after_confirm,
    route_after_review,
    route_after_understand,
)
from backend.app.graph.state import TripState
from backend.app.integrations.research_cache import ResearchCandidatesCache


def build_trip_graph(
    agents: Mapping[str, CompiledStateGraph],
    checkpointer: BaseCheckpointSaver | None = None,
    *,
    understand_model: BaseChatModel | None = None,
    research_cache: ResearchCandidatesCache | None = None,
) -> CompiledStateGraph:
    """复用已构建的四个 Agent，组装专业子图和总图。

    Understand 提取与合并需求；Clarify 暂停并将回答交回 Understand。
    Confirm 展示行程并暂停；确认后进入 Save，修改后返回 Understand。
    暂停恢复需要入口传入 checkpointer，并复用同一 thread_id。
    Reviewer 宽松审核基本需求；通过后 Confirm，明显问题最多修订一次。
    needs_user 或修订未解决的问题进入 Clarify，不强制放行。
    用户在 Confirm 接受或主动提出修改。
    Save 通过运行上下文的数据库 session 幂等保存。
    """
    required_agents = {"researcher", "context_analyst", "planner", "reviewer"}
    missing_agents = required_agents.difference(agents)
    if missing_agents:
        raise ValueError(f"缺少 Agent：{', '.join(sorted(missing_agents))}")

    builder = StateGraph(TripState, context_schema=TravelBuddyContext)

    builder.add_node("understand", UnderstandNode(understand_model))
    builder.add_node("clarify", ClarifyNode())
    builder.add_node(
        "researcher",
        ResearcherNode(
            graph=build_researcher_graph(agents["researcher"]), cache=research_cache
        ),
    )
    builder.add_node(
        "context_analyst",
        ContextAnalystNode(
            graph=build_context_analyst_graph(agents["context_analyst"])
        ),
    )
    builder.add_node(
        "planner", PlannerNode(graph=build_planner_graph(agents["planner"]))
    )
    builder.add_node(
        "reviewer", ReviewerNode(graph=build_reviewer_graph(agents["reviewer"]))
    )
    builder.add_node("confirm", ConfirmNode())
    builder.add_node("save", SaveNode())

    builder.add_edge(START, "understand")
    builder.add_conditional_edges(
        "understand",
        route_after_understand,
        {
            "clarify": "clarify",
            "researcher": "researcher",
            "context_analyst": "context_analyst",
        },
    )
    builder.add_edge("clarify", "understand")

    # 两支调研自行跳过仍有效的数据；统一汇合，避免只刷新一支时重复调用 Planner。
    builder.add_edge(["researcher", "context_analyst"], "planner")
    builder.add_edge("planner", "reviewer")
    builder.add_conditional_edges(
        "reviewer",
        route_after_review,
        {"confirm": "confirm", "planner": "planner", "clarify": "clarify"},
    )
    builder.add_conditional_edges(
        "confirm",
        route_after_confirm,
        {"save": "save", "understand": "understand"},
    )
    builder.add_edge("save", END)

    return builder.compile(checkpointer=checkpointer)
