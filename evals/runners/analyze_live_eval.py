"""Read only LangSmith runs belonging to our evaluation conversation IDs."""

import json
import logging
import os
import re
import warnings
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
logging.disable(logging.CRITICAL)
warnings.filterwarnings("ignore", category=DeprecationWarning)
path = max(
    (
        p
        for p in (ROOT / "evals/reports").glob("resume-*.json")
        if "-traces" not in p.stem
    ),
    key=lambda p: p.stat().st_mtime,
)
report = json.loads(path.read_text(encoding="utf-8"))
ids = {t["conversation_id"] for t in report["turns"]}
start = datetime.strptime(
    report["run"].removeprefix("resume-"), "%Y%m%dT%H%M%S"
).replace(tzinfo=UTC)
client = Client(timeout_ms=20000)
roots = list(
    client.list_runs(
        project_name=os.getenv("LANGSMITH_PROJECT", "TravelBuddy"),
        is_root=True,
        start_time=start,
        limit=100,
    )
)
results = []
for root in roots:
    meta = (root.extra or {}).get("metadata", {})
    if str(meta.get("thread_id")) not in ids:
        continue
    runs = list(
        client.list_runs(
            project_name=os.getenv("LANGSMITH_PROJECT", "TravelBuddy"),
            trace_id=root.trace_id,
        )
    )
    parents = {str(r.parent_run_id) for r in runs if r.parent_run_id}
    llms = [r for r in runs if r.run_type == "llm" and str(r.id) not in parents]
    tools = [
        r
        for r in runs
        if r.run_type == "tool"
        and r.name.startswith("maps_")
        and str(r.id) not in parents
    ]
    nodes = [
        {
            "name": r.name,
            "seconds": (r.end_time - r.start_time).total_seconds()
            if r.end_time
            else None,
        }
        for r in runs
        if r.parent_run_id == root.id
    ]
    item = {
        "id": str(root.id),
        "conversation_id": meta["thread_id"],
        "url": client.get_run_url(run=root),
        "start": root.start_time.isoformat(),
        "seconds": (root.end_time - root.start_time).total_seconds()
        if root.end_time
        else None,
        "error": bool(root.error),
        "llm_calls": len(llms),
        "amap_tool_calls": len(tools),
        "input_tokens": sum(r.prompt_tokens or 0 for r in llms),
        "output_tokens": sum(r.completion_tokens or 0 for r in llms),
        "tools": dict(Counter(r.name for r in tools)),
        "nodes": nodes,
        "tool_error_count": sum(
            bool(r.error)
            or any(
                s in json.dumps(r.outputs or {}, ensure_ascii=False)
                for s in ["CUQPS_", '"isError": true']
            )
            for r in tools
        ),
        "tool_error_codes": dict(
            Counter(
                code
                for r in tools
                for code in set(
                    re.findall(
                        r"CUQPS_[A-Z_]+|INVALID_USER_KEY|DAILY_QUERY_OVER_LIMIT",
                        json.dumps(r.outputs or {}),
                    )
                )
            )
        ),
    }
    results.append(item)
out = path.with_name(path.stem + "-traces.json")
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False, indent=2))
