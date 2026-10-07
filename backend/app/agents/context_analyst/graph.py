from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.context_analyst.nodes import AnalyzeContextNode
from backend.app.agents.context_analyst.state import ContextAnalystState
from backend.app.graph.context import TravelBuddyContext


def build_context_analyst_graph(agent: CompiledStateGraph) -> CompiledStateGraph:
    """将已构建的约束 Agent 注入子图执行节点。"""
    builder = StateGraph(ContextAnalystState, context_schema=TravelBuddyContext)
    builder.add_node("analyze_context", AnalyzeContextNode(agent))
    builder.add_edge(START, "analyze_context")
    builder.add_edge("analyze_context", END)
    return builder.compile()
