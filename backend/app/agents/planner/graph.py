from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.planner.nodes import PlanNode
from backend.app.agents.planner.state import PlannerState
from backend.app.graph.context import TravelBuddyContext


def build_planner_graph() -> CompiledStateGraph:
    """组装子图骨架；后续在这里创建、绑定模型和工具。"""
    builder = StateGraph(PlannerState, context_schema=TravelBuddyContext)
    builder.add_node("plan", PlanNode())
    builder.add_edge(START, "plan")
    builder.add_edge("plan", END)
    return builder.compile()
