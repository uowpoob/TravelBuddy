from langgraph.runtime import Runtime

from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.state import TripState
from backend.app.services.itineraries import (
    ItinerarySaveError,
    save_confirmed_itinerary,
)


class SaveNode:
    """保存用户确认后的行程。"""

    async def __call__(
        self,
        state: TripState,
        runtime: Runtime[TravelBuddyContext],
    ) -> dict[str, object]:
        """提交已确认方案的业务快照，回写记录 ID 与实际版本号。"""
        if state.get("confirmed") is not True:
            raise ItinerarySaveError("行程尚未确认，不能保存。")
        context = runtime.context
        if context.db is None:
            raise ItinerarySaveError("保存行程需要数据库 session。")
        result = await save_confirmed_itinerary(
            context.db,
            user_id=context.user_id,
            conversation_id=context.conversation_id,
            save_key=state.get("save_key"),
            trip_request=state.get("trip_request"),
            itinerary=state.get("itinerary"),
            candidates=state.get("candidates"),
            travel_constraints=state.get("travel_constraints"),
            review_result=state.get("review_result"),
        )
        return {
            "saved_itinerary_id": result.id,
            "saved_itinerary_version": result.version,
        }
