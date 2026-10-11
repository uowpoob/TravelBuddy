"""Real-service persistence, idempotency, lock, cache-fallback and route coalescing probes."""

import asyncio
import json
import logging
import time
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.config import MapSettings, Settings
from backend.app.core.runtime import loop_factory
from backend.app.db.session import create_engine
from backend.app.graph.checkpoints import open_checkpointer
from backend.app.integrations.amap_routes import AmapRouteClient
from backend.app.integrations.mcp import AmapMCPClient, AmapMCPSettings
from backend.app.models import Conversation, SavedItinerary
from backend.app.repositories.conversations import ConversationRepository
from backend.app.services.itineraries import save_confirmed_itinerary

ROOT = Path(__file__).resolve().parents[2]
logging.disable(logging.CRITICAL)
source = max(
    (
        p
        for p in (ROOT / "evals/reports").glob("resume-*.json")
        if "-traces" not in p.stem
    ),
    key=lambda p: p.stat().st_mtime,
)
data = json.loads(source.read_text(encoding="utf-8"))
result = {"source": source.name, "checks": []}


def check(name, passed, **details):
    row = {"name": name, "pass": bool(passed), **details}
    result["checks"].append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    (ROOT / "evals/reports/reliability-2026-10-11.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def main():
    settings = Settings()
    engine = create_engine(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    saved = [t for t in data["turns"] if t["response"].get("saved_itinerary_id")]
    try:
        # A separate process/saver reads checkpoints written by the API evaluation.
        async with open_checkpointer(settings) as saver:
            for turn in saved:
                cid = turn["conversation_id"]
                checkpoint = await saver.aget_tuple(
                    {"configurable": {"thread_id": cid}}
                )
                values = checkpoint.checkpoint["channel_values"]
                check(
                    "fresh_process_checkpoint_read",
                    values.get("saved_itinerary_id")
                    == turn["response"]["saved_itinerary_id"],
                    conversation_id=cid,
                )
            if saved:
                cid = saved[0]["conversation_id"]
                checkpoint = await saver.aget_tuple(
                    {"configurable": {"thread_id": cid}}
                )
                values = checkpoint.checkpoint["channel_values"]
                async with factory() as session:
                    uid = await session.scalar(
                        select(Conversation.user_id).where(Conversation.id == cid)
                    )
                    before = await session.scalar(
                        select(func.count())
                        .select_from(SavedItinerary)
                        .where(SavedItinerary.conversation_id == cid)
                    )

                async def save_again():
                    async with factory() as session:
                        return await save_confirmed_itinerary(
                            session,
                            user_id=uid,
                            conversation_id=cid,
                            **{
                                key: values[key]
                                for key in (
                                    "save_key",
                                    "trip_request",
                                    "itinerary",
                                    "candidates",
                                    "travel_constraints",
                                    "review_result",
                                )
                            },
                        )

                start = time.perf_counter()
                outcomes = await asyncio.gather(*(save_again() for _ in range(10)))
                elapsed = time.perf_counter() - start
                async with factory() as session:
                    after = await session.scalar(
                        select(func.count())
                        .select_from(SavedItinerary)
                        .where(SavedItinerary.conversation_id == cid)
                    )
                check(
                    "10_concurrent_idempotent_saves",
                    before == after and len({o.id for o in outcomes}) == 1,
                    requests=10,
                    before_rows=before,
                    after_rows=after,
                    seconds=round(elapsed, 3),
                )
                async with factory() as first, factory() as second:
                    one = await ConversationRepository(first).try_lock_messages(cid)
                    two = await ConversationRepository(second).try_lock_messages(cid)
                    await first.rollback()
                    three = await ConversationRepository(second).try_lock_messages(cid)
                    check(
                        "competing_message_lock_and_release", one and not two and three
                    )
        route_client = AmapRouteClient(MapSettings())
        requests = []

        async def record_request(request):
            requests.append(request.url.path)  # never store URL query/API key

        route_client.http.event_hooks["request"] = [record_request]
        try:
            start = time.perf_counter()
            routes = await asyncio.gather(
                *(
                    route_client.route(
                        (120.148, 30.25), (120.155, 30.245), "walking", "杭州"
                    )
                    for _ in range(10)
                )
            )
            elapsed = time.perf_counter() - start
            check(
                "10_concurrent_routes_one_http_request",
                len(requests) == 1 and all(r[0].paths for r in routes),
                consumers=10,
                upstream_http_requests=len(requests),
                seconds=round(elapsed, 3),
            )
            start = time.perf_counter()
            _, hit = await route_client.route(
                (120.148, 30.25), (120.155, 30.245), "walking", "杭州"
            )
            check(
                "route_memory_cache",
                hit and len(requests) == 1,
                warm_ms=round((time.perf_counter() - start) * 1000, 3),
            )
        finally:
            await route_client.close()
        fallback_settings = AmapMCPSettings().model_copy(
            update={"redis_url": SecretStr("redis://127.0.0.1:1/0")}
        )
        async with AmapMCPClient(fallback_settings) as client:
            start = time.perf_counter()
            response = await client.call_tool("maps_weather", {"city": "杭州"})
            check(
                "redis_connection_refused_mcp_fallback",
                not response.is_error and bool(response.content),
                seconds=round(time.perf_counter() - start, 3),
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=loop_factory)
