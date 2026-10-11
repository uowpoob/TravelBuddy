"""Real services, no model/tool mocks. Run from root with python -m evals.runners.live_resume_eval.

Creates dedicated evaluation accounts/conversations, preserves evidence, uses an
isolated Redis namespace (1h TTL), and never flushes existing cache/data.
HTTP uses ASGI in-process transport, not a browser or deployed-server load test.
"""

import asyncio
import json
import logging
import os
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
RUN = "resume-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
os.environ["GD_MCP_CACHE_NAMESPACE"] = "travelbuddy:eval:" + RUN
REPORT = ROOT / "evals/reports" / (RUN + ".json")
report = {
    "run": RUN,
    "transport": "ASGI; real PG, Redis, LLM, Amap",
    "checks": [],
    "cache": [],
    "turns": [],
}
logging.disable(logging.CRITICAL)


def persist():
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def emit(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)
    persist()


async def cache_benchmark():
    from redis.asyncio import Redis

    from backend.app.integrations.mcp import AmapMCPClient, AmapMCPSettings

    settings = AmapMCPSettings()
    async with Redis.from_url(
        settings.redis_url.get_secret_value(), protocol=2
    ) as redis:
        report["redis_ping"] = await redis.ping()
    cases = [
        ("maps_text_search", {"city": "杭州", "keywords": "西湖", "citylimit": True}),
        ("maps_weather", {"city": "杭州"}),
        (
            "maps_direction_walking",
            {"origin": "120.148000,30.250000", "destination": "120.155000,30.245000"},
        ),
    ]
    for name, args in cases:
        for i in range(5):
            pair = {"tool": name, "sample": i + 1}
            isolated = settings.model_copy(
                update={"cache_namespace": settings.cache_namespace + f":{name}:{i}"}
            )
            async with AmapMCPClient(isolated) as client:
                for label in ("cold", "warm"):
                    start = time.perf_counter()
                    result = await client.call_tool(name, args)
                    pair[label + "_ms"] = round((time.perf_counter() - start) * 1000, 3)
                    pair[label + "_is_error"] = bool(result.is_error)
                    # Exclude service-level failures hidden inside successful MCP envelopes.
                    payload = result.model_dump_json(by_alias=True)
                    pair[label + "_business_error"] = any(
                        x in payload
                        for x in [
                            "CUQPS_",
                            "INVALID_USER_KEY",
                            "DAILY_QUERY_OVER_LIMIT",
                        ]
                    )
                    if label == "cold":
                        original = payload
                    else:
                        pair["same_result"] = original == payload
                pair["ttl"] = await client._cache._redis.ttl(
                    client._cache.tool_key(name, args)
                )
            report["cache"].append(pair)
            emit(pair)
            await asyncio.sleep(0.3)


async def api_eval():
    from backend.app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        if app.state.trip_graph is None:
            raise RuntimeError("Real trip graph failed initialization")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://eval", timeout=330
        ) as client:

            async def req(label, method, path, expected=200, **kwargs):
                start = time.perf_counter()
                response = await client.request(method, path, **kwargs)
                item = {
                    "name": label,
                    "http": response.status_code,
                    "expected": expected,
                    "pass": response.status_code == expected,
                    "ms": round((time.perf_counter() - start) * 1000, 2),
                }
                report["checks"].append(item)
                persist()
                return response

            await req("health", "GET", "/health")
            await req("database_health", "GET", "/health/db")
            await req("unauthenticated", "GET", "/api/v1/conversations", 401)
            headers = []
            for suffix in ("owner", "other"):
                credentials = {
                    "username": RUN + "-" + suffix,
                    "password": secrets.token_urlsafe(24),
                }
                await req(
                    "register_" + suffix,
                    "POST",
                    "/api/v1/auth/register",
                    201,
                    json=credentials,
                )
                login = await req(
                    "login_" + suffix, "POST", "/api/v1/auth/login", json=credentials
                )
                headers.append(
                    {"Authorization": "Bearer " + login.json()["access_token"]}
                )
            owner, other = headers
            await req(
                "invalid_pagination",
                "GET",
                "/api/v1/conversations?limit=0",
                422,
                headers=owner,
            )
            await req("map_config", "GET", "/api/v1/maps/config", headers=owner)
            cases = [
                (
                    "hangzhou_1d_cold",
                    "2026年10月12日去杭州玩1天，2位成年人，步行，喜欢西湖景观和本地美食，每天2到3个地点即可。不需要住宿，不设预算，从杭州当地出发，其他由你合理安排。",
                ),
                (
                    "hangzhou_1d_repeat",
                    "2026年10月12日去杭州玩1天，2位成年人，步行，喜欢西湖景观和本地美食，每天2到3个地点即可。不需要住宿，不设预算，从杭州当地出发，其他由你合理安排。",
                ),
                (
                    "beijing_3d",
                    "2026年10月13日起去北京玩3天，1位成年人，公共交通，喜欢历史文化和胡同美食，每天2到3个景点，节奏轻松。北京当地出发，无必去景点，不设预算，不需要安排酒店，其他由你合理安排。",
                ),
            ]

            async def turn(case, cid, content):
                start = time.perf_counter()
                response = await req(
                    case,
                    "POST",
                    f"/api/v1/conversations/{cid}/messages",
                    headers=owner,
                    json={"content": content},
                )
                elapsed = time.perf_counter() - start
                data = response.json()
                item = {
                    "case": case,
                    "conversation_id": cid,
                    "seconds": round(elapsed, 3),
                    "http": response.status_code,
                    "status": data.get("status"),
                    "response": data,
                }
                report["turns"].append(item)
                emit({k: v for k, v in item.items() if k != "response"})
                return data

            for case, prompt in cases:
                created = await req(
                    "create_" + case,
                    "POST",
                    "/api/v1/conversations",
                    201,
                    headers=owner,
                    json={"title": "实测 " + case},
                )
                cid = created.json()["id"]
                await req(
                    "isolation_" + case,
                    "GET",
                    f"/api/v1/conversations/{cid}",
                    404,
                    headers=other,
                )
                data = await turn(case, cid, prompt)
                if data.get("status") == "waiting_clarification":
                    data = await turn(
                        case + "_clarification",
                        cid,
                        "无额外要求，按照我刚才给出的日期、人数和交通方式安排，不设预算，不需要住宿，其他由你决定。",
                    )
                if data.get("status") == "waiting_approval":
                    intr = data["interrupt"]
                    candidates = intr["candidates"]
                    ids = {
                        p["id"]
                        for group in candidates.values()
                        if isinstance(group, list)
                        for p in group
                    }
                    days = intr["itinerary"]["days"]
                    report["checks"].append(
                        {
                            "name": case + "_valid_days_and_references",
                            "pass": len(days) == intr["trip_request"]["days"]
                            and all(
                                d["visits"]
                                and all(v["place_id"] in ids for v in d["visits"])
                                for d in days
                            ),
                        }
                    )
                    if case == "hangzhou_1d_cold":
                        data = await turn(
                            case + "_modify",
                            cid,
                            "目的地、日期、人数、交通方式和兴趣不变，把每个景点的停留时间减少15分钟，不增加或替换地点。",
                        )
                    if data.get("status") == "waiting_approval":
                        saved = await turn(case + "_save", cid, "确认")
                        iid = saved.get("saved_itinerary_id")
                        if iid:
                            await req(
                                case + "_saved_detail",
                                "GET",
                                f"/api/v1/itineraries/{iid}",
                                headers=owner,
                            )
                            await req(
                                case + "_saved_isolation",
                                "GET",
                                f"/api/v1/itineraries/{iid}",
                                404,
                                headers=other,
                            )
                            route = await req(
                                case + "_routes",
                                "GET",
                                f"/api/v1/itineraries/{iid}/routes?day=1&mode=walking",
                                headers=owner,
                            )
                            report.setdefault("routes", []).append(
                                {"case": case, "response": route.json()}
                            )
                reread = await req(
                    case + "_checkpoint_read",
                    "GET",
                    f"/api/v1/conversations/{cid}/messages",
                    headers=owner,
                )
                report.setdefault("checkpoint_reads", []).append(
                    {
                        "case": case,
                        "status": reread.json().get("status"),
                        "total": reread.json().get("total"),
                    }
                )
            # Missing-info path exercises real model extraction without full planning.
            c = await req(
                "create_incomplete",
                "POST",
                "/api/v1/conversations",
                201,
                headers=owner,
                json={"title": "实测缺少需求"},
            )
            data = await turn("incomplete", c.json()["id"], "想去成都玩")
            report["checks"].append(
                {
                    "name": "incomplete_clarifies",
                    "pass": data.get("status") == "waiting_clarification",
                }
            )
    emit({"finished": True, "report": str(REPORT)})


async def main():
    await cache_benchmark()
    await api_eval()
    if not all(row["pass"] for row in report["checks"]):
        raise RuntimeError("One or more real API checks failed; inspect the report")


if __name__ == "__main__":
    from backend.app.core.runtime import loop_factory

    try:
        asyncio.run(main(), loop_factory=loop_factory)
    except Exception as exc:  # noqa: BLE001 -- avoid printing credentials in SDK errors
        report["fatal_error_type"] = type(exc).__name__
        emit({"fatal_error_type": type(exc).__name__})
        raise SystemExit(1) from None
