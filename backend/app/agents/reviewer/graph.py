from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.reviewer.nodes import ReviewNode
from backend.app.agents.reviewer.state import ReviewerState
from backend.app.graph.context import TravelBuddyContext


def build_reviewer_graph(agent: CompiledStateGraph) -> CompiledStateGraph:
    """将已构建的审核 Agent 注入子图执行节点。"""
    builder = StateGraph(ReviewerState, context_schema=TravelBuddyContext)
    builder.add_node("review", ReviewNode(agent))
    builder.add_edge(START, "review")
    builder.add_edge("review", END)
    return builder.compile()
