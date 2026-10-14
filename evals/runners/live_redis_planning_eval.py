"""Ten real API cold/warm planning pairs; no model, MCP, or Redis mocks.

Run: .venv/Scripts/python.exe -m evals.runners.live_redis_planning_eval
Creates a dedicated account and conversations, retains checkpoints/evidence.
Each pair uses a fresh Redis namespace; never flushes or deletes existing data.
Instrumentation delegates to the original implementation without changing results.
"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import sys
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from mcp.types import CallToolResult

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
SMOKE = "--smoke" in sys.argv
RUN = ("research-cache-smoke-" if SMOKE else "redis-planning-") + datetime.now(
    ZoneInfo("Asia/Shanghai")
).strftime("%Y%m%dT%H%M%S")
NAMESPACE = "travelbuddy:eval:" + RUN
os.environ["GD_MCP_CACHE_NAMESPACE"] = NAMESPACE + ":startup"
os.environ["GD_MCP_CACHE_ENABLED"] = "true"
REPORT = ROOT / "evals/reports" / (RUN + ".json")
ACTIVE: ContextVar[dict | None] = ContextVar("eval_turn", default=None)
CALL: ContextVar[dict | None] = ContextVar("eval_mcp_call", default=None)
report = {
    "run": RUN,
    "started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
    "transport": "FastAPI HTTPX ASGI; real model, Amap MCP, Redis, PostgreSQL/checkpoints",
    "method": "Identical prompts in fresh cold/warm conversations and isolated Redis namespaces; --smoke runs one Hangzhou pair",
    "pairs": [],
}
logging.disable(logging.CRITICAL)


def persist():
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def emit(data):
    persist()
    print(json.dumps(data, ensure_ascii=False), flush=True)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def business_errors(payload):
    markers = [
        "CUQPS_HAS_EXCEEDED_THE_LIMIT",
        "INVALID_USER_KEY",
        "DAILY_QUERY_OVER_LIMIT",
        "USER_DAILY_QUERY_OVER_LIMIT",
        "SERVICE_NOT_AVAILABLE",
        "INVALID_PARAMS",
        "UNKNOWN_ERROR",
        "INSUFFICIENT_PRIVILEGES",
        "USERKEY_PLAT_NOMATCH",
    ]
    errors = [marker for marker in markers if marker in payload]
    # Detect Amap business failure envelopes inside MCP text blocks too.
    envelope = json.loads(payload)
    for block in envelope.get("content", []):
        if block.get("type") != "text":
            continue
        try:
            body = json.loads(block.get("text", ""))
        except (ValueError, TypeError):
            continue
        if isinstance(body, dict) and str(body.get("status")) == "0":
            errors.append(str(body.get("info", "AMAP_STATUS_0")))
    return sorted(set(errors))


def install_instrumentation(mcp):
    original_get = mcp._cache.get
    original_call = mcp.call_tool
    original_session = mcp._session

    async def observed_get(key):
        start = time.perf_counter()
        value = await original_get(key)
        row = CALL.get()
        if row is not None:
            row["redis_read_ms"] = (time.perf_counter() - start) * 1000
            row["redis_value_present"] = value is not None
            if value is not None:
                try:
                    cached = CallToolResult.model_validate_json(value)
                    row["cache_hit"] = not cached.is_error
                except ValueError:
                    row["cache_hit"] = False
        return value

    @asynccontextmanager
    async def observed_session():
        row = CALL.get()
        if row is not None:
            row["upstream_sessions"] += 1
        async with original_session() as session:
            yield session

    async def observed_call(name, arguments=None):
        row = {
            "tool": name,
            "arguments": arguments or {},
            "cache_hit": False,
            "cache_eligible": mcp._cache.tool_key(name, arguments or {}) is not None,
            "upstream_sessions": 0,
        }
        token = CALL.set(row)
        start = time.perf_counter()
        try:
            result = await original_call(name, arguments)
            payload = result.model_dump_json(by_alias=True)
            row.update(
                is_error=bool(result.is_error),
                business_errors=business_errors(payload),
                result_sha256=digest(payload),
                response_bytes=len(payload.encode("utf-8")),
            )
            return result
        except Exception as exc:
            row["exception_type"] = type(exc).__name__
            raise
        finally:
            row["ms"] = (time.perf_counter() - start) * 1000
            current = ACTIVE.get()
            if current is not None:
                current["mcp_calls"].append(row)
            CALL.reset(token)

    mcp._cache.get = observed_get
    mcp._session = observed_session
    mcp.call_tool = observed_call

    # The production callback is still executed; add timing/model evidence only.
    from backend.app.services import messages
    from backend.app.services.planning import PlanningProgressRecorder

    class ObservedProgress(PlanningProgressRecorder):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.llm_starts = {}
            self.node_starts = {}

        async def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
            self.llm_starts[run_id] = time.perf_counter()

        async def on_llm_end(self, response, *, run_id, **kwargs):
            current = ACTIVE.get()
            start = self.llm_starts.pop(run_id, None)
            if current is not None and start is not None:
                usages = []
                for generation in response.generations:
                    for value in generation:
                        message = getattr(value, "message", None)
                        if message is not None and message.usage_metadata:
                            usages.append(message.usage_metadata)
                current["model_calls"].append(
                    {
                        "run_id": str(run_id),
                        "seconds": time.perf_counter() - start,
                        "usage": usages,
                    }
                )

        async def on_llm_error(self, error, *, run_id, **kwargs):
            current = ACTIVE.get()
            start = self.llm_starts.pop(run_id, None)
            if current is not None:
                current["model_calls"].append(
                    {
                        "run_id": str(run_id),
                        "error_type": type(error).__name__,
                        "seconds": time.perf_counter() - start if start else None,
                    }
                )

        async def on_chain_start(
            self, serialized, inputs, *, run_id, parent_run_id=None, name=None, **kwargs
        ):
            if parent_run_id == self.root_id and name in self.node_names:
                self.node_starts[run_id] = (name, time.perf_counter())
            await super().on_chain_start(
                serialized,
                inputs,
                run_id=run_id,
                parent_run_id=parent_run_id,
                name=name,
                **kwargs,
            )

        async def on_chain_end(self, outputs, *, run_id, **kwargs):
            started = self.node_starts.pop(run_id, None)
            current = ACTIVE.get()
            if started is not None and current is not None:
                current["nodes"].append(
                    {"name": started[0], "seconds": time.perf_counter() - started[1]}
                )
            await super().on_chain_end(outputs, run_id=run_id, **kwargs)

    messages.PlanningProgressRecorder = ObservedProgress


CASES = [
    ("杭州西湖1日", "杭州", 1, "步行", "西湖景观和本地美食"),
    ("杭州文化2日", "杭州", 2, "公共交通", "历史文化和茶文化"),
    ("北京历史2日", "北京", 2, "公共交通", "历史文化和胡同美食"),
    ("上海漫步1日", "上海", 1, "步行", "外滩建筑和城市漫步"),
    ("苏州园林2日", "苏州", 2, "公共交通", "古典园林和江南文化"),
    ("南京文化1日", "南京", 1, "公共交通", "历史文化和当地美食"),
    ("成都休闲2日", "成都", 2, "公共交通", "公园休闲和四川美食"),
    ("西安古城2日", "西安", 2, "公共交通", "古城历史和陕西美食"),
    ("厦门海滨1日", "厦门", 1, "步行", "海滨风景和城市漫步"),
    ("广州美食1日", "广州", 1, "公共交通", "岭南文化和粤菜美食"),
]


def summarize(row):
    calls = row["mcp_calls"]
    eligible = [c for c in calls if c["cache_eligible"]]
    hits = sum(c["cache_hit"] for c in eligible)
    invalid = [
        c
        for c in calls
        if c.get("is_error") or c.get("business_errors") or c.get("exception_type")
    ]
    row["metrics"] = {
        "model_calls": len(row["model_calls"]),
        "mcp_calls": len(calls),
        "eligible_calls": len(eligible),
        "cache_hits": hits,
        "hit_rate_pct": 100 * hits / len(eligible) if eligible else None,
        "upstream_tool_calls": sum(c["upstream_sessions"] for c in calls),
        "tool_seconds_sum": sum(c["ms"] for c in calls) / 1000,
        "business_or_tool_errors": len(invalid),
        "cached_error_hits": sum(c["cache_hit"] for c in invalid),
    }


async def main():
    emit({"stage": "loading_real_application"})
    from redis.asyncio import Redis

    from backend.app.core.config import Settings
    from backend.app.integrations.mcp import AmapMCPSettings
    from backend.app.main import create_app

    settings = Settings()
    mcp_settings = AmapMCPSettings()
    report.update(
        model=settings.DEEPSEEK_MODEL,
        cache_ttl_seconds=mcp_settings.cache_ttl_seconds,
        checkpoint_postgres=bool(settings.LANGGRAPH_PG_DSN.get_secret_value()),
    )
    async with Redis.from_url(
        mcp_settings.redis_url.get_secret_value(),
        protocol=2,
        socket_connect_timeout=5,
        socket_timeout=5,
    ) as redis:
        report["redis_ping"] = await redis.ping()
        report["redis_version"] = (await redis.info("server"))["redis_version"]
        report["redis_url_source"] = "REDIS_URL environment or project configuration"
    emit({"stage": "initializing_mcp_and_postgres", "redis": report["redis_ping"]})
    app = create_app()
    async with app.router.lifespan_context(app):
        if app.state.trip_graph is None:
            raise RuntimeError("Real graph initialization failed")
        mcp = app.state.amap_mcp_client
        install_instrumentation(mcp)
        research_cache = app.state.research_cache
        original_lookup = research_cache.get_candidates

        async def observed_lookup(request, source_messages=None):
            start = time.perf_counter()
            candidates = await original_lookup(request, source_messages)
            row = ACTIVE.get()
            if row is not None:
                row["research_cache_lookups"].append(
                    {
                        "hit": candidates is not None,
                        "ms": (time.perf_counter() - start) * 1000,
                        "key": research_cache.key_for(request, source_messages),
                    }
                )
            return candidates

        research_cache.get_candidates = observed_lookup
        cases = CASES[:1] if SMOKE else CASES
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://eval", timeout=330
        ) as api:
            credentials = {"username": RUN, "password": secrets.token_urlsafe(24)}
            registered = await api.post("/api/v1/auth/register", json=credentials)
            if registered.status_code != 201:
                raise RuntimeError("Evaluation account registration failed")
            login = await api.post("/api/v1/auth/login", json=credentials)
            login.raise_for_status()
            api.headers["Authorization"] = "Bearer " + login.json()["access_token"]
            report["evaluation_username"] = credentials["username"]
            health = await api.get("/health/db")
            report["database_health_http"] = health.status_code
            health.raise_for_status()
            emit(
                {
                    "started": RUN,
                    "model": report["model"],
                    "redis": report["redis_ping"],
                    "cases": len(cases),
                }
            )
            for index, (label, city, days, transport, interests) in enumerate(cases, 1):
                namespace = NAMESPACE + f":case{index:02d}"
                mcp._cache._prefix = namespace
                research_cache._prefix = namespace
                assert not [
                    key
                    async for key in mcp._cache._redis.scan_iter(match=namespace + ":*")
                ]
                prompt = (
                    f"2026年10月14日起去{city}玩{days}天，2位成年人，{transport}，喜欢{interests}，"
                    f"每天2到3个游览地点，节奏轻松。{city}当地出发，无必须去的地点，不设预算，"
                    "不需要安排酒店，不需要城际交通。请直接生成完整行程，其他细节由你合理安排。"
                )
                pair = {
                    "index": index,
                    "case": label,
                    "prompt": prompt,
                    "namespace": namespace,
                    "turns": {},
                    "exact_replays": [],
                }
                report["pairs"].append(pair)
                for phase in ("cold", "warm"):
                    created = await api.post(
                        "/api/v1/conversations",
                        json={"title": f"缓存评测 {index} {phase}"},
                    )
                    created.raise_for_status()
                    cid = created.json()["id"]
                    row = {
                        "conversation_id": cid,
                        "mcp_calls": [],
                        "model_calls": [],
                        "nodes": [],
                        "attempts": [],
                        "research_cache_lookups": [],
                    }
                    pair["turns"][phase] = row
                    token = ACTIVE.set(row)
                    start = time.perf_counter()
                    try:
                        content = prompt
                        # A real clarification counts in total time; never silently discard it.
                        for attempt in range(2):
                            attempt_start = time.perf_counter()
                            response = await api.post(
                                f"/api/v1/conversations/{cid}/messages",
                                json={"content": content},
                            )
                            data = response.json()
                            row["attempts"].append(
                                {
                                    "http": response.status_code,
                                    "seconds": time.perf_counter() - attempt_start,
                                    "response": data,
                                }
                            )
                            if (
                                response.status_code != 200
                                or data.get("status") != "waiting_clarification"
                            ):
                                break
                            content = "无额外要求，请按最初给出的日期、天数、人数、交通方式和兴趣生成行程，不设预算、不需要住宿，其他由你合理安排。"
                        row.update(
                            seconds=time.perf_counter() - start,
                            http=response.status_code,
                            status=data.get("status"),
                        )
                        intr = data.get("interrupt") or {}
                        row["trip_request"] = intr.get("trip_request")
                        row["itinerary_days"] = len(
                            (intr.get("itinerary") or {}).get("days", [])
                        )
                        row["complete_plan"] = (
                            row["http"] == 200
                            and row["status"] == "waiting_approval"
                            and row["itinerary_days"] == days
                        )
                    finally:
                        ACTIVE.reset(token)
                    summarize(row)
                    emit(
                        {
                            "case": label,
                            "phase": phase,
                            "seconds": round(row["seconds"], 3),
                            "status": row["status"],
                            **row["metrics"],
                        }
                    )
                cold, warm = pair["turns"]["cold"], pair["turns"]["warm"]
                pair["valid_complete_pair"] = (
                    cold["complete_plan"] and warm["complete_plan"]
                )
                pair["observed_reduction_pct"] = (
                    100 * (cold["seconds"] - warm["seconds"]) / cold["seconds"]
                    if pair["valid_complete_pair"]
                    else None
                )
                pair["same_extracted_request"] = (
                    cold["trip_request"] == warm["trip_request"]
                )
                pair["same_candidates"] = (
                    cold["attempts"][-1]["response"].get("interrupt") or {}
                ).get("candidates") == (
                    warm["attempts"][-1]["response"].get("interrupt") or {}
                ).get("candidates")
                pair["research_cache_ttl"] = await research_cache._redis.ttl(
                    cold["research_cache_lookups"][0]["key"]
                )
                # Strict same-argument evidence, separate from full planning and its model variation.
                seen = set()
                for call in cold["mcp_calls"]:
                    signature = json.dumps(
                        [call["tool"], call["arguments"]],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    if (
                        signature in seen
                        or call["cache_hit"]
                        or call.get("business_errors")
                        or call.get("is_error")
                        or "result_sha256" not in call
                    ):
                        continue
                    seen.add(signature)
                    replay = {"mcp_calls": []}
                    token = ACTIVE.set(replay)
                    try:
                        await mcp.call_tool(call["tool"], call["arguments"])
                    finally:
                        ACTIVE.reset(token)
                    hot_call = replay["mcp_calls"][0]
                    key = mcp._cache.tool_key(call["tool"], call["arguments"])
                    pair["exact_replays"].append(
                        {
                            "tool": call["tool"],
                            "arguments": call["arguments"],
                            "cold_ms": call["ms"],
                            "warm_ms": hot_call["ms"],
                            "cache_hit": hot_call["cache_hit"],
                            "upstream_sessions": hot_call["upstream_sessions"],
                            "same_result": hot_call.get("result_sha256")
                            == call["result_sha256"],
                            "business_errors": hot_call.get("business_errors"),
                            "ttl": await mcp._cache._redis.ttl(key) if key else None,
                        }
                    )
                emit(
                    {
                        "pair_done": index,
                        "case": label,
                        "reduction_pct": pair["observed_reduction_pct"],
                        "same_extracted_request": pair["same_extracted_request"],
                        "exact_replays": len(pair["exact_replays"]),
                    }
                )
    report["finished_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    report["finished"] = True
    emit({"finished": True, "report": str(REPORT)})


if __name__ == "__main__":
    from backend.app.core.runtime import loop_factory

    try:
        asyncio.run(main(), loop_factory=loop_factory)
    except Exception as exc:  # noqa: BLE001 -- avoid secrets in SDK exceptions
        report["fatal_error_type"] = type(exc).__name__
        emit({"fatal_error_type": type(exc).__name__, "report": str(REPORT)})
        raise SystemExit(1) from None
