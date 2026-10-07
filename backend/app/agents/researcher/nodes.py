from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.researcher.state import ResearcherState
from backend.app.graph.context import TravelBuddyContext
from backend.app.schemas.place import Candidates


class ResearchNode:
    """调用已构建的地点 Agent，将结构化输出写入子图。"""

    def __init__(self, agent: CompiledStateGraph):
        self.agent = agent

    async def __call__(
        self,
        state: ResearcherState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        message = HumanMessage(content=state["trip_request"].model_dump_json())
        result = await self.agent.ainvoke(
            {"messages": [message]}, config=config, context=runtime.context
        )
        return {
            "messages": result["messages"],
            "candidates": Candidates.model_validate(result["structured_response"]),
        }
