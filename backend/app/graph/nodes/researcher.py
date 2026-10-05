
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
    ) -> dict[str, object]:
        agent_input: ResearcherState = {
            "messages": [],
            "trip_request": state["trip_request"],
        }
        result = await self.agent.ainvoke(agent_input, context=runtime.context)
        # 只提取业务输出；占位节点尚未生成的字段不返回，内部 messages 不回传。
        return {key: result[key] for key in ["candidates"] if key in result}
