from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.reviewer.nodes import ReviewNode
from backend.app.agents.reviewer.state import ReviewerState
from backend.app.graph.context import TravelBuddyContext


def build_reviewer_graph() -> CompiledStateGraph:
    """组装子图骨架；后续在这里创建、绑定模型和工具。"""
    builder = StateGraph(ReviewerState, context_schema=TravelBuddyContext)
    builder.add_node("review", ReviewNode())
    builder.add_edge(START, "review")
    builder.add_edge("review", END)
    return builder.compile()
