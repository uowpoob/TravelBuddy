"""Summarize retained real Redis/planning evidence (no external calls)."""

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def write_markdown(source, report, summary, rows):
    def n(value, digits=2):
        return f"{value:.{digits}f}" if value is not None else "N/A"

    lines = [
        "# Redis 缓存与完整规划真实冷热对照",
        "",
        f"运行 `{report['run']}`，北京时间 {report['started_at']} 至 {report.get('finished_at', '尚未结束')}。",
        "",
        f"有效完整规划对照 **{summary['valid_full_planning_pairs']} 组**；冷规划平均 **{n(summary['average_cold_seconds'], 3)} 秒**，热规划平均 **{n(summary['average_warm_seconds'], 3)} 秒**，总体平均耗时下降 **{n(summary['aggregate_observed_reduction_pct'])}%**。负值表示变慢。",
        "",
        f"热轮 Redis 命中率 **{n(summary['warm_hit_rate_pct'])}%（{summary['warm_hits']}/{summary['warm_queries']}）**；缓存业务错误命中 {summary['warm_cached_errors']} 次。冷轮命中 {summary['cold_hits']}/{summary['cold_queries']} 次。",
        "",
        "| 场景 | 冷规划/秒 | 热规划/秒 | 耗时下降 | 热轮命中/查询 | 热轮命中率 | 模型调用 冷→热 | 高德错误 冷→热 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            f"| {r['case']} | {r['cold_seconds']:.3f} | {r['warm_seconds']:.3f} | {n(r['observed_reduction_pct'])}% | {r['warm_hits']}/{r['warm_queries']} | {n(r['warm_hit_rate_pct'])}% | {r['cold_model_calls']}→{r['warm_model_calls']} | {r['cold_errors']}→{r['warm_errors']} |"
        )
    lines += [
        "",
        "## 严格同工具、同参数验证",
        "",
        f"重放冷轮实际产生的未命中且未检测到业务错误的唯一查询。共 **{summary['exact_replay_total']} 个**；其中 **{summary['exact_replay_verified']} 个**满足 Redis 命中、无新增 MCP 上游会话、响应 SHA-256 完全一致、无已检测业务错误。",
        "",
        f"严格同参数查询冷延迟中位数 **{n(summary['exact_replay_cold_median_ms'], 3)} ms**，热延迟中位数 **{n(summary['exact_replay_warm_median_ms'], 3)} ms**，中位延迟下降 **{n(summary.get('exact_replay_median_reduction_pct'), 4)}%**。冷延迟包含未命中、真实 MCP 会话初始化、上游查询和写入；热延迟包含 Redis 读取、反序列化与少量观测开销。",
        "",
        "## 测试口径与解释",
        "",
        f"- 实际模型 `{report.get('model')}`、高德 Streamable HTTP MCP、PostgreSQL 与检查点、Redis {report.get('redis_version')}。本轮使用本机临时 Redis 实例 127.0.0.1:6381，TTL {report.get('cache_ttl_seconds')} 秒；没有 mock 模型、地图或缓存结果。",
        "- FastAPI 真实生命周期 + HTTPX ASGI transport，覆盖注册登录、消息 API、业务层、需求理解、地点调研与天气分析、Planner、Reviewer、进度存储与检查点。计时从消息发送至完整方案进入 waiting_approval，含必要澄清；不含建会话、用户确认保存、应用启动或浏览器/Nginx/Uvicorn 网络开销。",
        "- 10 组分别使用独立 namespace，冷轮之前确认无 key；冷热均建立全新会话，用户文本完全相同。原始工具参数重放在对应冷热完整规划完成后执行，不提前预热热规划。未清空既有缓存，未删除既有数据。",
        f"- 核心结构化参数完全相等的对照为 {summary['core_parameters_matching_pairs']}/{summary['complete_pairs']} 组。完整需求中偏好和附加要求可能被模型重新归类。原始文本、提取结果、完整行程响应、节点耗时、模型调用/用量、每次 MCP 参数、命中、上游会话和错误均保留在 JSON。",
        "- Redis 缓存 MCP 查询结果，键包含工具名和完整参数；模型与整份行程仍重新生成。相同城市、相同提问不保证相同工具参数。完整规划耗时差混合了缓存、模型生成、查询数量、审核路径与上游波动，因此是本次重复提问的观测差异，不能全部归因于 Redis。",
        f"- 两轮均未检测到业务/工具错误的完整对照有 {summary['error_free_pairs']} 组。表中错误包括高德 QPS 限流；完成规划不代表所有地图请求成功或行程质量完全通过验收。严格同参数统计排除已检测错误响应。",
        "- 每场景仅一对样本，不推导稳定 SLA、生产命中率或 P95。命中率分母是可缓存 MCP 工具调用数，排除工具发现；不是整个 Redis 服务的 INFO 全局计数。",
        f"- 耗时下降 = (冷耗时 − 热耗时) / 冷耗时 × 100%；总体平均下降按有效组冷/热总耗时计算。逐组降幅中位数 {n(summary['median_pair_observed_reduction_pct'])}%。并行工具时间之和可能大于 API 墙钟时间，不能直接相减。",
        "",
        "## 证据和复现",
        "",
        f"[原始记录]({source.name}) · [汇总 JSON]({source.with_suffix('.summary.json').name}) · [逐组 CSV]({source.with_suffix('.csv').name})。原始记录包含专用测试用户名与会话 ID，不包含认证令牌或 API 密钥。",
        "",
        "```powershell",
        "$env:REDIS_URL = 'redis://127.0.0.1:6381/0'  # 或配置一个可连接的真实 Redis",
        ".\\.venv\\Scripts\\python.exe -u -m evals.runners.live_redis_planning_eval",
        ".\\.venv\\Scripts\\python.exe -m evals.runners.analyze_redis_planning_eval "
        + str(source.relative_to(ROOT)),
        "```",
        "",
        "重新执行会调用实际模型/地图服务并创建新的评测用户与会话。未来复测需更新脚本中的旅行日期。",
    ]
    source.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    source = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else max(
            (
                p
                for p in (ROOT / "evals/reports").glob("redis-planning-*.json")
                if not p.name.endswith(".summary.json")
            ),
            key=lambda p: p.stat().st_mtime,
        )
    )
    source = source.resolve()
    report = json.loads(source.read_text(encoding="utf-8"))
    pairs = [
        p
        for p in report["pairs"]
        if set(p["turns"]) == {"cold", "warm"}
        and all("metrics" in t for t in p["turns"].values())
    ]
    valid = [p for p in pairs if p["valid_complete_pair"]]
    rows = []
    core_fields = (
        "destination_city",
        "departure_city",
        "start_date",
        "days",
        "travelers",
        "transport",
        "budget",
        "budget_scope",
    )
    for pair in pairs:
        cold, warm = pair["turns"]["cold"], pair["turns"]["warm"]
        cm, wm = cold["metrics"], warm["metrics"]
        rows.append(
            {
                "case": pair["case"],
                "cold_seconds": round(cold["seconds"], 3),
                "warm_seconds": round(warm["seconds"], 3),
                "observed_reduction_pct": round(pair["observed_reduction_pct"], 2)
                if pair["observed_reduction_pct"] is not None
                else None,
                "cold_hits": cm["cache_hits"],
                "cold_queries": cm["eligible_calls"],
                "warm_hits": wm["cache_hits"],
                "warm_queries": wm["eligible_calls"],
                "warm_hit_rate_pct": round(wm["hit_rate_pct"], 2)
                if wm["hit_rate_pct"] is not None
                else None,
                "cold_model_calls": cm["model_calls"],
                "warm_model_calls": wm["model_calls"],
                "cold_upstream_calls": cm["upstream_tool_calls"],
                "warm_upstream_calls": wm["upstream_tool_calls"],
                "cold_errors": cm["business_or_tool_errors"],
                "warm_errors": wm["business_or_tool_errors"],
                "warm_cached_errors": wm["cached_error_hits"],
                "cold_status": cold["status"],
                "warm_status": warm["status"],
                "same_extracted_request": pair["same_extracted_request"],
                "same_core_parameters": all(
                    (cold.get("trip_request") or {}).get(k)
                    == (warm.get("trip_request") or {}).get(k)
                    for k in core_fields
                ),
                "warm_valid_hit_rate_pct": round(
                    100
                    * (wm["cache_hits"] - wm["cached_error_hits"])
                    / wm["eligible_calls"],
                    2,
                )
                if wm["eligible_calls"]
                else None,
            }
        )
    cold_seconds = sum(p["turns"]["cold"]["seconds"] for p in valid)
    warm_seconds = sum(p["turns"]["warm"]["seconds"] for p in valid)
    warm_queries = sum(p["turns"]["warm"]["metrics"]["eligible_calls"] for p in pairs)
    warm_hits = sum(p["turns"]["warm"]["metrics"]["cache_hits"] for p in pairs)
    replays = [r for p in pairs for r in p["exact_replays"]]
    verified = [
        r
        for r in replays
        if r["cache_hit"]
        and r["same_result"]
        and r["upstream_sessions"] == 0
        and not r["business_errors"]
    ]
    clean_pairs = [
        p
        for p in valid
        if all(
            t["metrics"]["business_or_tool_errors"] == 0 for t in p["turns"].values()
        )
    ]
    summary = {
        "source": source.name,
        "finished": report.get("finished", False),
        "complete_pairs": len(pairs),
        "valid_full_planning_pairs": len(valid),
        "error_free_pairs": len(clean_pairs),
        "average_cold_seconds": cold_seconds / len(valid) if valid else None,
        "average_warm_seconds": warm_seconds / len(valid) if valid else None,
        "aggregate_observed_reduction_pct": 100
        * (cold_seconds - warm_seconds)
        / cold_seconds
        if cold_seconds
        else None,
        "median_pair_observed_reduction_pct": statistics.median(
            p["observed_reduction_pct"] for p in valid
        )
        if valid
        else None,
        "warm_hits": warm_hits,
        "warm_queries": warm_queries,
        "warm_hit_rate_pct": 100 * warm_hits / warm_queries if warm_queries else None,
        "warm_valid_result_hits": sum(
            p["turns"]["warm"]["metrics"]["cache_hits"]
            - p["turns"]["warm"]["metrics"]["cached_error_hits"]
            for p in pairs
        ),
        "warm_cached_errors": sum(
            p["turns"]["warm"]["metrics"]["cached_error_hits"] for p in pairs
        ),
        "cold_hits": sum(p["turns"]["cold"]["metrics"]["cache_hits"] for p in pairs),
        "cold_queries": sum(
            p["turns"]["cold"]["metrics"]["eligible_calls"] for p in pairs
        ),
        "core_parameters_matching_pairs": sum(r["same_core_parameters"] for r in rows),
        "exact_replay_total": len(replays),
        "exact_replay_verified": len(verified),
        "exact_replay_cold_median_ms": statistics.median(r["cold_ms"] for r in verified)
        if verified
        else None,
        "exact_replay_warm_median_ms": statistics.median(r["warm_ms"] for r in verified)
        if verified
        else None,
    }
    if verified:
        summary["exact_replay_median_reduction_pct"] = 100 * (
            1
            - summary["exact_replay_warm_median_ms"]
            / summary["exact_replay_cold_median_ms"]
        )
    output = source.with_suffix(".summary.json")
    output.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with source.with_suffix(".csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    write_markdown(source, report, summary, rows)
    print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
