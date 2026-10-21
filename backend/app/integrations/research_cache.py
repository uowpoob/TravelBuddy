"""缓存已完成的地点调研；命中时无需重新运行 Researcher。"""

import hashlib
import json
import logging
import math
import unicodedata

from pydantic import ValidationError

from backend.app.integrations.mcp.cache import RedisMCPCache
from backend.app.integrations.mcp.config import AmapMCPSettings
from backend.app.prompts.researcher import SYSTEM_PROMPT
from backend.app.schemas.place import Candidates
from backend.app.schemas.trip import TripRequest

logger = logging.getLogger(__name__)
_PACE_REQUIREMENTS = frozenset({"节奏轻松", "节奏紧凑"})


def _text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def usable_candidates(candidates: Candidates) -> bool:
    places = [
        place for name in Candidates.model_fields for place in getattr(candidates, name)
    ]
    if not places:
        return False
    for place in places:
        if (
            not all(value.strip() for value in (place.id, place.name, place.category))
            or place.source != "amap"
        ):
            return False
        try:
            longitude, latitude = map(float, place.location.split(","))
        except ValueError:
            return False
        if not (
            math.isfinite(longitude)
            and math.isfinite(latitude)
            and -180 <= longitude <= 180
            and -90 <= latitude <= 90
        ):
            return False
    return True


class ResearchCandidatesCache(RedisMCPCache):
    """沿用 MCP Redis 配置、TTL 和故障降级，独立的版本化缓存键。

    有用户消息时使用完整需求历史、标量条件和必去地点；没有消息的
    直接图调用使用全部 TripRequest 字段。不猜测不同文字的语义。
    """

    def __init__(self, settings: AmapMCPSettings) -> None:
        super().__init__(
            settings.model_copy(
                update={
                    "cache_enabled": settings.cache_enabled
                    and settings.research_cache_enabled,
                }
            )
        )
        self._policy = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()

    def key_for(
        self,
        request: TripRequest,
        source_messages: list[str] | None = None,
        interest_description: str = "",
    ) -> str | None:
        if self._redis is None:
            return None
        payload = request.model_dump(mode="json")
        payload["user_interests"] = _text(interest_description)
        # 仅处理已观测到的节奏描述分类漂移，不混淆一般偏好与硬约束。
        pace = set()
        for field in ("preferences", "additional_requirements"):
            values = {_text(value) for value in payload[field] if _text(value)}
            pace.update(values & _PACE_REQUIREMENTS)
            payload[field] = sorted(values - _PACE_REQUIREMENTS)
        payload["pace_requirements"] = sorted(pace)
        payload["must_visit"] = sorted(
            {_text(value) for value in payload["must_visit"] if _text(value)}
        )
        if source_messages:
            # 完整用户消息历史已包含兴趣与硬要求。避免相同原文被模型
            # 改写/补充礼貌性要求后失配；标量条件和必去地点仍校验。
            for field in (
                "preferences",
                "additional_requirements",
                "pace_requirements",
            ):
                payload.pop(field)
            payload["source_messages"] = [_text(value) for value in source_messages]
        for name, value in payload.items():
            if isinstance(value, str):
                payload[name] = _text(value)
        serialized = json.dumps(
            {"request": payload, "policy": self._policy},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{self._prefix}:research:candidates:v1:{fingerprint}"

    async def get_candidates(
        self,
        request: TripRequest,
        source_messages: list[str] | None = None,
        interest_description: str = "",
    ) -> Candidates | None:
        # 有用户消息时只用完整消息索引，避免模型漏提取新限制后误用旧结果。
        key = self.key_for(request, source_messages, interest_description)
        if key is None:
            return None
        value = await self.get(key)
        if value is None:
            return None
        try:
            candidates = Candidates.model_validate_json(value)
        except ValidationError:
            logger.warning("地点调研缓存无效，重新调研。")
            return None
        if not usable_candidates(candidates):
            logger.warning("地点调研缓存缺少有效地点，重新调研。")
            return None
        logger.info("命中地点调研缓存，复用候选地点。")
        return candidates

    async def set_candidates(
        self,
        request: TripRequest,
        candidates: Candidates,
        source_messages: list[str] | None = None,
        interest_description: str = "",
    ) -> None:
        key = self.key_for(request, source_messages, interest_description)
        if key is not None and usable_candidates(candidates):
            await self.set(key, candidates.model_dump_json())
