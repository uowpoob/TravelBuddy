from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.context_analyst.state import ContextAnalystState
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class ContextAnalystNode:
    """调用出行约束子图，只将约束结果交回主图。"""

    def __init__(self, graph: CompiledStateGraph):
        self.graph = graph

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        if state.get("context_required") is False:
            return {}
        graph_input: ContextAnalystState = {
            "messages": [],
            "trip_request": state["trip_request"],
        }
        result = await self.graph.ainvoke(
            graph_input, config=config, context=runtime.context
        )
        # 内部消息留在子图，主图仅接收结构化约束。
        return {
            "travel_constraints": result["travel_constraints"],
            "context_required": False,
        }
