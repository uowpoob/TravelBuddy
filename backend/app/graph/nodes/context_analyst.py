from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.context_analyst.state import ContextAnalystState
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState


class ContextAnalystNode:
    """调用出行约束子图，只将约束结果交回主图。"""

    def __init__(self, agent: CompiledStateGraph):
        self.agent = agent

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        agent_input: ContextAnalystState = {
            "messages": [],
            "trip_request": state["trip_request"],
        }
        result = await self.agent.ainvoke(agent_input, context=runtime.context)
        # 只提取业务输出；占位节点尚未生成的字段不返回，内部 messages 不回传。
        return {key: result[key] for key in ["travel_constraints"] if key in result}
