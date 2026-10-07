from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.researcher.state import ResearcherState
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class ResearcherNode:
    """调用地点调研子图，只将候选地点交回主图。"""

    def __init__(self, agent: CompiledStateGraph):
        self.agent = agent

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        agent_input: ResearcherState = {
            "messages": [],
            "trip_request": state["trip_request"],
        }
        result = await self.agent.ainvoke(
            agent_input, config=config, context=runtime.context
        )
        # 内部消息留在子图，主图仅接收候选地点。
        return {"candidates": result["candidates"]}
