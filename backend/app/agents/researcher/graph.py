from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents.researcher.nodes import ResearchNode
from backend.app.agents.researcher.state import ResearcherState
from backend.app.graph.context import TravelBuddyContext


def build_researcher_graph(agent: CompiledStateGraph) -> CompiledStateGraph:
    """将已构建的地点 Agent 注入子图执行节点。"""
    builder = StateGraph(ResearcherState, context_schema=TravelBuddyContext)
    builder.add_node("research", ResearchNode(agent))
    builder.add_edge(START, "research")
    builder.add_edge("research", END)
    return builder.compile()
