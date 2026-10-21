from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.researcher.state import ResearcherState
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState
from backend.app.integrations.research_cache import ResearchCandidatesCache
from backend.app.schemas.place import Candidates


class ResearcherNode:
    """调用地点调研子图，只将候选地点交回主图。"""

    def __init__(
        self, graph: CompiledStateGraph, cache: ResearchCandidatesCache | None = None
    ):
        self.graph = graph
        self.cache = cache

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
        config: RunnableConfig,
    ) -> dict[str, object]:
        if state.get("research_required") is False:
            return {}
        graph_input: ResearcherState = {
            "messages": [],
            "trip_request": state["trip_request"],
        }
        previous = state.get("candidates")
        source_messages = [
            str(message.text)
            for message in state.get("messages", [])
            if isinstance(message, HumanMessage)
        ]
        candidates = (
            await self.cache.get_candidates(
                state["trip_request"],
                source_messages,
                runtime.context.interest_description,
            )
            if self.cache is not None and not state.get("research_cache_bypass", False)
            else None
        )
        if candidates is None:
            result = await self.graph.ainvoke(
                graph_input, config=config, context=runtime.context
            )
            # 内部消息留在子图，主图仅接收候选地点。
            candidates = result["candidates"].model_copy(deep=True)
            if self.cache is not None:
                # 写入本次调研结果，不能混入下方合并的历史行程地点。
                await self.cache.set_candidates(
                    state["trip_request"],
                    candidates,
                    source_messages,
                    runtime.context.interest_description,
                )
        # 旧行程仍可能引用原候选。保留其真实地点数据，Planner 决定是否继续安排。
        if previous is not None and state.get("itinerary") is not None:
            used_ids = {
                visit.place_id
                for day in state["itinerary"].days
                for visit in day.visits
            }
            seen = {
                place.id
                for places in (
                    candidates.attractions,
                    candidates.restaurants,
                    candidates.hotels,
                )
                for place in places
            }
            for category in Candidates.model_fields:
                for place in getattr(previous, category):
                    if place.id in used_ids and place.id not in seen:
                        getattr(candidates, category).append(place)
                        seen.add(place.id)
        if not (candidates.attractions or candidates.restaurants or candidates.hotels):
            raise ValueError(
                "地点调研没有得到可用地点，暂时无法生成具体行程，请重试地点调研。"
            )
        return {
            "candidates": candidates,
            "research_required": False,
            "research_cache_bypass": False,
        }
