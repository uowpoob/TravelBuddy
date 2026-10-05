from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.context_analyst.nodes import AnalyzeContextNode
from backend.app.agents.context_analyst.state import ContextAnalystState
from backend.app.graph.context import TravelBuddyContext


def build_context_analyst_graph() -> CompiledStateGraph:
    """组装子图骨架；后续在这里创建、绑定模型和工具。"""
    builder = StateGraph(ContextAnalystState, context_schema=TravelBuddyContext)
    builder.add_node("analyze_context", AnalyzeContextNode())
    builder.add_edge(START, "analyze_context")
    builder.add_edge("analyze_context", END)
    return builder.compile()
