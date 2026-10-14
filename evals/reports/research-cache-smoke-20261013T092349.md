# Researcher 候选缓存实现与真实冷热测试

运行 `research-cache-smoke-20261013T092349`；北京时间 2026-10-13T09:23:49.950486+08:00 至 2026-10-13T09:24:35.535747+08:00。

缓存完整 Candidates（景点、餐厅、酒店的真实 POI 数据）。API 和终端图均已接入。命中后跳过 Researcher 子图，天气、Planner 与 Reviewer 继续运行。

缓存使用现有 Redis URL、namespace、超时、故障降级和 TTL，默认 3600 秒。`GD_RESEARCH_CACHE_ENABLED=false` 可独立关闭。键包含完整用户需求历史、标量旅行参数、必去地点及 Researcher 提示词指纹；没有用户消息的直接图调用按完整 TripRequest 构造键。只做空白/顺序等确定性规范化，不将不同措辞猜测为相同需求。

候选需非空、关键字段完整、坐标有效且来源为 amap。空/损坏/无效缓存或 Redis 故障触发真实调研。缓存写入发生在历史行程地点合并之前，避免其他会话拿到历史地点；用户明确要求更换已有候选时绕过缓存。

## 最终有效对照

场景：2026-10-14 杭州西湖一日游，2 位成年人、步行、不安排酒店。新账号、两次新会话、同一完整问题，独立且初始为空的 Redis namespace。真实 deepseek-flash、高德 MCP、PostgreSQL/检查点、Redis 3.2.100（本机临时端口 6381），没有 mock；通过 FastAPI HTTPX ASGI 运行完整业务链路。

| 指标 | 冷轮 | 热轮 |
| --- | ---: | ---: |
| 完整规划耗时 | 31.739 秒 | 9.064 秒 |
| Researcher 节点耗时 | 23.801 秒 | 16.743 毫秒 |
| Researcher 地点工具调用 | 28 | 0 |
| 全流程模型调用 | 15 | 6 |
| 全流程上游 MCP 查询 | 32 | 0 |
| 候选缓存 | 未命中 | 命中 |
| 规划结果 | waiting_approval | waiting_approval |

完整规划观测耗时下降 **71.44%**；候选数据逐字段完全一致，冷热命中同一候选 key，检测时 TTL 3584 秒。热轮 4 次 MCP 工具调用均命中底层缓存，因此没有额外上游 MCP 查询；Understand、天气分析、Planner、Reviewer 仍实际调用模型。

冷轮检测到 5 次高德 QPS 限流，热轮 0 次。该数据是一组观测值，包含上游与模型波动，不是稳定性能保证；未做关闭高层缓存的随机 A/B。本次关键验证是热轮确实跳过 Researcher，复用了同一份候选。

## 检查与其他尝试

- 最终针对性测试：21 passed、1 skipped（旧测试的 opt-in Redis smoke 未启用）；Ruff 与 git diff --check 通过。
- 既有 test_agent_handoff.py：6 passed、3 failed。以 HEAD 的原 ResearcherNode 和 builder 运行相同测试，仍有完全相同的 3 项失败：两项 Reviewer 输入字段旧断言、Planner 空结构化响应的异常类型旧断言。未修改这些旧测试。
- [首次测试](research-cache-smoke-20261013T091706.json)：相同原文被模型多提取一条泛化要求，原结构化缓存键失配。随后用完整用户需求历史构造稳定索引，并保留标量参数与必去地点校验。
- [第二次测试](research-cache-smoke-20261013T092222.json)：热轮已命中，但冷轮在 Planner 阶段返回 502，未计为有效完整对照，也未用其时间计算提升百分比。
- 临时 Redis 已关闭；专用测试会话和原始记录保留用于复查。

## 证据与复现

[完整原始记录](research-cache-smoke-20261013T092349.json) · [机器可读汇总](research-cache-smoke-20261013T092349.summary.json)。记录包含缓存命中/键、模型用量、工具参数、候选、行程与节点耗时，不含令牌或 API 密钥。

```powershell
$env:REDIS_URL = 'redis://127.0.0.1:6381/0' # 需先启动实际 Redis，或使用自己的地址
$env:GD_RESEARCH_CACHE_ENABLED = 'true'
.\.venv\Scripts\python.exe -u -m evals.runners.live_redis_planning_eval --smoke
.\.venv\Scripts\python.exe -m pytest backend/tests/integrations/test_research_candidates_cache.py backend/tests/integrations/test_mcp_redis_cache.py -q
```

未来复测请更新脚本中的旅行日期。运行会调用实际模型与地图服务并创建独立评测数据。
