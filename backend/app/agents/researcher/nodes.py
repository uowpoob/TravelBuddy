import json
import logging

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from backend.app.agents.researcher.state import ResearcherState
from backend.app.graph.context import TravelBuddyContext
from backend.app.schemas.place import Candidates, Place

logger = logging.getLogger(__name__)


def candidates_from_details(messages: list[BaseMessage]) -> Candidates:
    """模型漏填候选时，仅从成功 POI 详情的真实字段恢复已选地点。"""
    candidates = Candidates()
    seen = set()
    for message in messages:
        if (
            not isinstance(message, ToolMessage)
            or message.name != "maps_search_detail"
            or message.status == "error"
        ):
            continue
        payloads = [message.content]
        if isinstance(message.artifact, dict):
            payloads.extend(
                block.get("text")
                for block in message.artifact.get("content", [])
                if isinstance(block, dict) and block.get("type") == "text"
            )
            payloads.append(message.artifact.get("structuredContent"))
        for payload in payloads:
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except ValueError:
                    continue
            if not isinstance(payload, dict):
                continue
            fields = ("id", "name", "location", "type")
            if not all(
                isinstance(payload.get(field), str) and payload[field].strip()
                for field in fields
            ):
                continue
            if payload["id"] in seen:
                continue
            # 只接受有效经纬度，不把错误响应或地址当作坐标。
            try:
                longitude, latitude = map(float, payload["location"].split(","))
            except ValueError:
                continue
            if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                continue
            place = Place(
                id=payload["id"],
                name=payload["name"],
                location=payload["location"],
                category=payload["type"],
                address=payload.get("address")
                if isinstance(payload.get("address"), str)
                else "",
            )
            primary_type = place.category.split(";")[0]
            category = (
                "hotels"
                if primary_type == "住宿服务"
                else "restaurants"
                if primary_type == "餐饮服务"
                else "attractions"
            )
            getattr(candidates, category).append(place)
            seen.add(place.id)
    return candidates


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
        candidates = Candidates.model_validate(result["structured_response"])
        if not (candidates.attractions or candidates.restaurants or candidates.hotels):
            candidates = candidates_from_details(result["messages"])
            if candidates.attractions or candidates.restaurants or candidates.hotels:
                logger.warning(
                    "Researcher 输出空候选，已从成功详情响应恢复地点：景点 %d、餐厅 %d、酒店 %d。",
                    len(candidates.attractions),
                    len(candidates.restaurants),
                    len(candidates.hotels),
                )
        return {
            "messages": result["messages"],
            "candidates": candidates,
        }
