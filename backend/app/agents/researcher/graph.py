from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.researcher.nodes import ResearchNode
from backend.app.agents.researcher.state import ResearcherState
from backend.app.graph.context import TravelBuddyContext


def build_researcher_graph() -> CompiledStateGraph:
    """组装子图骨架；后续在这里创建、绑定模型和工具。"""
    builder = StateGraph(ResearcherState, context_schema=TravelBuddyContext)
    builder.add_node("research", ResearchNode())
    builder.add_edge(START, "research")
    builder.add_edge("research", END)
    return builder.compile()
