from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.planner.nodes import PlanNode
from backend.app.agents.planner.state import PlannerState
from backend.app.graph.context import TravelBuddyContext


def build_planner_graph(agent: CompiledStateGraph) -> CompiledStateGraph:
    """将已构建的规划 Agent 注入子图执行节点。"""
    builder = StateGraph(PlannerState, context_schema=TravelBuddyContext)
    builder.add_node("plan", PlanNode(agent))
    builder.add_edge(START, "plan")
    builder.add_edge("plan", END)
    return builder.compile()
