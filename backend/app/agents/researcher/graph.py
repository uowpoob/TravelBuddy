from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.researcher.nodes import ResearchNode
from backend.app.agents.researcher.state import ResearcherState
from backend.app.graph.context import TravelBuddyContext


def build_researcher_graph() -> CompiledStateGraph:
    """组装地点调研子图骨架；节点执行逻辑后续实现。"""
    builder = StateGraph(ResearcherState, context_schema=TravelBuddyContext)
    builder.add_node("research", ResearchNode())
    builder.add_edge(START, "research")
    builder.add_edge("research", END)
    return builder.compile()
