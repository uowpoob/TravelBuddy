# TravelBuddy

Python 基础项目，使用 uv 管理依赖与项目虚拟环境。

## 环境

- Python 3.13
- 虚拟环境：`.venv`
- 依赖声明：`pyproject.toml`
- 依赖锁文件：`uv.lock`（提交到 Git）

## 常用命令

```powershell
uv sync
uv run python examples/hello.py
uv add <包名>
uv add --dev <开发工具包名>
```

若终端找不到 uv，可使用 `& "$env:USERPROFILE\.local\bin\uv.exe"` 替代上述命令中的 `uv`。

## PyCharm

打开本目录，选择 `.venv\Scripts\python.exe` 作为项目解释器。
使用模块运行配置 `backend`，工作目录选择项目根目录；参数可填 `--reload`。
入门示例移至 `examples/hello.py`，不再作为后端入口。

## 启动后端

```powershell
uv run python -m backend --reload
```

- 健康检查：http://127.0.0.1:8000/health
- 接口文档：http://127.0.0.1:8000/docs

健康检查返回 HTTP 200 和 `{"status":"ok","service":"TravelBuddy"}`。
此接口只检查 API 进程是否正常响应，不调用模型或高德服务。

## 注册与登录

已实现 `POST /api/v1/auth/register`、`POST /api/v1/auth/login` 和
`GET /api/v1/auth/me`，复用现有 users 表。密码只保存加盐哈希，登录返回 Bearer JWT。
本地签名密钥初始化命令为 `uv run python -m backend.scripts.init_auth`，已有密钥不会被覆盖。
默认令牌有效期 60 分钟，修改 .env 后需重启后端。
可在 `/docs` 中注册、登录并使用 Authorize 调用 me。
请求格式、返回字段和后续接口鉴权方式见 [AUTH.md](docs/AUTH.md)。

## 会话接口

已实现 `POST /api/v1/conversations`，使用 Bearer JWT 归属于当前登录用户。
发送 `{"title":"杭州周末游"}` 或 `{}`（默认“新旅行”），成功返回 201 和会话 UUID、
标题及时间。
`GET /api/v1/conversations?offset=0&limit=20` 按更新时间倒序查询当前用户的会话列表；
`GET /api/v1/conversations/{conversation_id}` 查看详情，不存在或不属于当前用户时返回 404。
`GET /api/v1/conversations/{conversation_id}/messages` 分页查看对话及澄清/确认状态；
`POST /api/v1/conversations/{conversation_id}/messages` 发送 `{"content":"想去杭州"}`，
等待本轮暂停或完成后一次性返回 JSON。相同接口支持回答澄清问题、确认或修改方案，
未完成的失败步骤可发送 `{"retry":true}` 恢复。
请求格式与分层说明见 [CONVERSATIONS.md](docs/CONVERSATIONS.md)。

## 前端会话联调

前端已接入会话创建、列表、历史消息、需求澄清、方案修改、确认保存和失败步骤恢复。
启动后端后，在另一个终端运行：

```powershell
cd frontend
npm run dev
```

打开 http://127.0.0.1:5173，登录后可在首页填写旅行需求并点击“开始规划”，
或通过侧栏“旅行会话”新建、继续会话。开发代理默认指向 http://127.0.0.1:8000，
可通过 `frontend/.env.local` 中的 `API_PROXY_TARGET` 修改。
详细测试流程及错误恢复说明见 [FRONTEND_CONVERSATIONS.md](docs/FRONTEND_CONVERSATIONS.md)。

## 在终端测试旅行图

不启动前端或 HTTP 服务，直接输入需求、回答澄清问题、确认并保存：

```powershell
uv run python -m backend.scripts.trip_chat --message "想去杭州"
```

默认创建本地调试用户和会话；实际调用已配置的模型和高德 MCP。
终端显示节点进度、工具名称、确认方案和已保存 ID/版本；支持 `/state`、`/retry`、`/quit`。
配置 PostgreSQL checkpoint 后可使用用户 ID 和会话 ID 重新打开并恢复。
完整准备步骤、单轮运行及 PyCharm 配置见 [GRAPH_DEBUG.md](docs/GRAPH_DEBUG.md)。

## 本地调用高德 MCP

后端的 `backend/app/integrations/mcp/` 通过 Streamable HTTP 直接连接高德 MCP。
接入地址来自[高德官方接入文档](https://lbs.amap.com/api/mcp-server/gettingstarted)。
`mcp_server/` 保留，后续将 TravelBuddy 完成的行程规划、修改等业务能力封装为对外工具；
当前调用高德不需要启动本地 MCP Server。前端继续通过 FastAPI 业务 API 获取结果。

在根目录 `.env` 中配置高德 Web 服务 Key；已有 `GD_API_KEY` 可直接复用。
以下两个配置可选，未填写时使用所示默认值：

```dotenv
GD_API_KEY=YOUR_AMAP_WEB_SERVICE_KEY
GD_MCP_URL=https://mcp.amap.com/mcp
GD_MCP_TIMEOUT_SECONDS=30
```

客户端自动将 Key 加入鉴权参数，`GD_MCP_URL` 不需要填写密钥。
配置与错误信息不打印鉴权 URL，SDK 的 HTTP 日志会隐藏此 Key。
超时按每个 MCP 请求计算。每次操作在同一异步任务内建立和关闭会话，
FastAPI 启动时，应用、高德与 DeepSeek 配置完整则统一执行工具发现并创建四个 Agent，
保存在 `app.state.agents`，并注入四个专业子图，组装后缓存总图到 `app.state.trip_graph`。
初始化不执行模型推理、地点、天气或路线查询。
未配置必要字段，或高德发现、模型、checkpoint 初始化失败时，旅行流程保持未就绪并记录不含密钥的日志；
这些初始化失败不阻止 API 健康检查。修正配置后重启后端，重新初始化。

在项目根目录执行：

```powershell
# List all tools, including their descriptions and JSON schemas.
uv run python -m backend.scripts.amap_mcp list

# Save the discovered tools and their full schemas for inspection.
uv run python -m backend.scripts.amap_mcp list --output .local/amap-tools.json

# Example: use this only if list returns maps_weather with a city parameter.
uv run python -m backend.scripts.amap_mcp call maps_weather --arguments '{"city":"杭州"}'

# Alternatively, read a JSON object from a UTF-8 file.
uv run python -m backend.scripts.amap_mcp call maps_weather --arguments-file ./weather-arguments.json
```

工具名称与参数以 `list` 返回的实际 schema 为准；不写参数时发送空 JSON 对象。
`--arguments` 与 `--arguments-file` 只能选择一个。
命令不依赖数据库、DeepSeek 或正在运行的 FastAPI。
结果输出保留原始 MCP 的 `content`、`structuredContent` 和 `isError`，
工具执行失败或连接失败时返回非零退出码。已实际执行工具发现并获取 15 个工具，
完整列表保存于本地 `.local/amap-tools.json`；该文件是发现时的快照，重新运行命令可更新。
尚未运行真实模型调用或高德业务工具调用。

Python 调用入口为 `AmapMCPClient()` 的 `await client.list_tools()` 和
`await client.call_tool(name, arguments)`；返回 SDK 原生类型，工具失败检查
`result.is_error`。FastAPI 路由可通过 `get_amap_mcp_client` 依赖获取同一客户端配置；
未配置 Key 时该依赖返回 503。Researcher 和 Context Analyst 的工具绑定工厂已实现；
Planner 的路线工具绑定工厂也已实现。统一组装函数位于 `backend/app/agents/builder.py`；
已由 `backend/app/lifespan.py` 在启动时调用。四个专业节点现已调用缓存 Agent，
将结构化输出交回总图；普通流程节点、预算估算和前端业务接口仍待后续实现。
Reviewer 首版只读已有证据，不绑定外部工具。

MCP 工具到 LangChain 工具的适配位于 `backend/app/integrations/mcp/adapter.py`。
在异步函数中可以分步获取并适配：

```python
from backend.app.integrations.mcp import AmapMCPClient
from backend.app.integrations.mcp.adapter import adapt_amap_tools

client = AmapMCPClient()
mcp_tools = await client.list_tools()
agent_tools = adapt_amap_tools(mcp_tools, client)
```

`adapt_amap_tools` 保留高德的名称、描述和输入 JSON Schema，将调用绑定到
`client.call_tool`。它本身不执行网络请求；`load_amap_tools(client)` 是将发现与
适配合并的异步入口。返回的 `StructuredTool` 供后续按角色筛选后交给 `create_agent`。
工具仅提供异步执行入口，应使用 `ainvoke` 或 Agent 的异步执行方式。
成功调用向模型返回文本及结构化数据，完整 MCP 响应保存在 `ToolMessage.artifact`；
连接或服务端工具执行失败转换为 `ToolException`，由 LangChain 返回工具错误。
真实模型和高德业务工具调用尚未运行验证。

创建多个 Agent 时统一获取并适配一次工具列表，不由每个角色单独加载。
生命周期在配置完整时执行以下初始化，后续请求复用返回的 Agent：

```python
app.state.agents = await build_agents(app.state.amap_mcp_client)
saver = await checkpoint_stack.enter_async_context(open_checkpointer(settings))
app.state.trip_graph = build_trip_graph(app.state.agents, checkpointer=saver)
```

后续路由可使用 `Depends(get_agents)`，或显式调用
`backend.app.api.dependencies.get_agents(request)` 获取缓存字典。
字典键为 researcher、context_analyst、planner、reviewer；未初始化时依赖返回 503，
不会重新创建 Agent。不要在每次请求中再次调用 `build_agents`。

`build_agents` 内部只调用一次 `load_amap_tools(client)`，再将同一份工具列表
传给 Researcher、Context Analyst、Planner 的构建函数。各角色 tools.py 只保留
工具名称和同步 select 函数，从内存列表筛选，缺少必要工具时明确报错。
Reviewer 构建时不接收外部工具。角色工厂保留结构化输出和可选 checkpointer。

`build_trip_graph(agents, checkpointer=None)` 将字典中的 Agent 传给各专业子图的
执行节点。节点把所需业务输入编码成 JSON 用户消息，异步调用 Agent，校验
`structured_response` 并写入子图状态。总图包装节点只接收 candidates、
travel_constraints、itinerary、review_result 和 clarification_question，
内部模型与工具消息留在专业子图。Planner 修订时携带旧行程和审核意见。
接口可用 `Depends(get_trip_graph)` 获取缓存总图；未就绪时返回 503。
Save 已接入业务数据库，审核自动修订最多两轮；非流式旅行运行/恢复已通过消息 HTTP 接口接入。
生命周期已接入 checkpoint，并在关闭时释放 saver。

Understand 已实现：读取最新一条用户消息、已有 TripRequest、近期对话和审核意见，
通过结构化模型提取本轮更新的字段，再由 Python 合并需求与检查必填项。
未提及的字段保持原值，支持明确清除字段；新旅行从空需求开始，清理旧行程状态。
按天调整等额外要求写入 TripRequest.additional_requirements。
当前必填项为目的地、出行日期、1–5 天的天数、人数和交通方式；给出预算时，
还需明确总额或人均口径。出发城市和预算可以留空。
缺失项或模型识别的歧义生成 clarification_question，并路由到 Clarify。
每次重新理解需求会重置审核、确认和修订状态；修改当前行程时保留旧行程供规划参考。
模型在首次需要提取时加载；build_trip_graph 的 understand_model 参数可注入测试模型。

Clarify 已实现动态暂停：`interrupt` 返回 JSON 问题，包含 `type="clarify"`、
`question`、`missing_fields` 和 `issues`。问题优先使用已有澄清问题；没有时依据
缺失字段、审核问题或通用提示生成。调用方通过 `result["__interrupt__"][0].value`
展示问题，再使用相同 `thread_id` 和 `Command(resume="用户回答")` 恢复。
回答必须是非空字符串，会去除两端空白；无效回答抛出 `pydantic.ValidationError`，
可以用同一 thread 重试，不追加消息或进入 Understand。
有效回答将问题和回答分别写入 AIMessage / HumanMessage，经既有边回到 Understand；
若信息仍不完整，会再次暂停。

Confirm 已实现行程展示与动态暂停。载荷包含 `type="confirm"`、`question`、
`summary`、`trip_request`、`itinerary` 和 `candidates`；文本摘要依据实际地点名称、
每日活动、停留及交通耗时、预计费用和备注生成，未知费用显示尚未估算。
没有行程或行程天数列表为空时会报错，不能确认空方案。
使用同一 `thread_id` 和 `Command(resume="确认")` 恢复后，完整匹配确认用语
（如确认、同意、可以、好的、OK）时设置 `confirmed=True`，经现有路由进入 Save。
其他非空文本作为修改反馈，设置 `confirmed=False` 并返回 Understand；
例如 `Command(resume="第二天下午换成室内活动")`。
回答包含“确认”但同时提出修改时不会按确认处理；空白或非文本回答校验失败，可重试。
恢复后才将展示的方案和原始回答写入对话，让 Understand 理解修改针对的具体方案。
Save 已实现：确认后检查完整需求、行程天数和地点引用，并验证会话属于当前用户，
在数据库事务中保存需求、行程、候选地点及可选约束/审核快照。
Planner 完成方案时生成 `save_key` 并写入 State；Confirm 暂停和 Save 重试复用该标识。
同一会话的同一标识返回已有记录，内容不同则拒绝覆盖；新标识保存为下一个版本。
会话行锁保护并发版本分配，提交成功后回写 `saved_itinerary_id` 和 `saved_itinerary_version`。
保存需要已有的用户、UUID 会话，以及 `TravelBuddyContext.db` 中专供 Save、未开启事务的
`AsyncSession`；预览和澄清阶段可以不传 db。没有数据库、未确认或数据无效时明确报错。
完整事务、恢复和测试说明见 [DATABASE.md](docs/DATABASE.md#save-接入)。
本次 Confirm 实现按用户要求未新增或运行测试。

以下代码在异步函数中运行，`graph` 为缓存主图，`context` 为 TravelBuddyContext：

```python
from langchain_core.messages import HumanMessage
from langgraph.types import Command

config = {"configurable": {"thread_id": "trip-001"}}
result = await graph.ainvoke(
    {"messages": [HumanMessage(content="想去杭州")]},
    config=config,
    context=context,
)
question = result["__interrupt__"][0].value["question"]
result = await graph.ainvoke(
    Command(resume="2026-10-10 出发，玩两天"),
    config=config,
    context=context,
)
# 仍缺人数和交通方式时，result 中会再次出现 __interrupt__。
```

独立构建图时须传入 checkpointer；应用生命周期根据 `LANGGRAPH_PG_DSN` 使用
PostgreSQL saver，未配置时使用内存 saver。内存只能在当前进程中恢复；
PostgreSQL 表须先用现有初始化脚本建立。消息 HTTP 接口会自动恢复澄清/确认暂停。

模型结构化输出统一从 `backend/app/schemas/structured_output.py` 导入：
Understand 使用专用的 RequestUnderstanding；四个专业 Agent 分别使用 Candidates、
TravelConstraints、Itinerary、ReviewResult。后四个直接导出既有业务类，同时用于
总图 State 字段，保持同一份字段定义。各业务类的文档字符串标注了其输出角色和状态字段。

| Agent | 外部工具 | 结构化输出 |
| --- | --- | --- |
| Researcher | maps_text_search、maps_around_search、maps_search_detail、maps_geo | Candidates |
| Context Analyst | maps_weather | TravelConstraints |
| Planner | maps_direction_walking、maps_direction_driving、maps_direction_bicycling、maps_direction_transit_integrated、maps_distance | Itinerary |
| Reviewer | 无，首版只读已有证据 | ReviewResult |

Researcher 提示词要求先查真实 POI 再筛选，地址解析坐标不能直接作为有 ID 的候选。
Context Analyst 按天气工具实际返回的日期匹配旅行区间，区分实况和预报，说明未覆盖日期。
Planner 用真实候选坐标和对应交通方式查询路线，将明确耗时换算成分钟；
不能把直线距离当作实际路线耗时，也不能把部分交通费用当作完整旅行总费用。

统一的是创建 Agent 时的工具发现流程；实际业务工具调用仍请求高德。
当前客户端每次 call_tool 建立独立会话并读取工具元信息，尚未复用会话或缓存发现结果。
build_agents 已接入 FastAPI 生命周期；关闭应用时清除 Agent、客户端和 session 工厂缓存，
并释放数据库引擎。核心配置模块不再在导入时实例化 Settings，模型配置延迟到创建模型时读取。
四个专业内部节点已使用缓存 Agent；Understand、Clarify、Confirm 和 Save 已实现。
测试使用模拟模型验证结构化结果交接，不执行真实模型、天气或路线查询。

## PostgreSQL

业务数据使用 SQLAlchemy 访问，业务表变更使用 Alembic 管理；LangGraph 检查点由
`langgraph-checkpoint-postgres` 单独管理。已定义三张业务表：

- `users`：用户账号、唯一用户名、密码哈希和时间戳。
- `conversations`：用户的聊天会话，UUID 的字符串形式作为 LangGraph `thread_id`。
- `itineraries`：用户确认后的行程版本，保存需求、行程和地点信息的 JSONB 快照。

首个迁移版本为 `118ebaead2fc`；最新版本 `c6a1e7d4b930` 为行程增加 `save_key`
和会话内唯一约束。完整字段、约束和 Save 接入说明见
[DATABASE.md](docs/DATABASE.md)。Save、注册登录和创建会话已实现；
会话列表、详情、消息查看和非流式旅行运行/恢复也已实现；独立行程查询 API 仍待实现。

本地 `.env` 的 `DATABASE_DSN` 指向独立的 `travelbuddy` 数据库。
连接账号可复用现有本地 PostgreSQL 账号，但不要指向其他项目的数据库。
新环境可复制 `.env.example` 为 `.env` 后填写连接信息；不要覆盖已有 `.env`。
`python -m backend` 已配置 Windows 下 psycopg 所需的 SelectorEventLoop。
此配置既支持 PostgreSQL URI，也支持 psycopg 的 `host=... dbname=...` 格式。

`DATABASE_DSN` 用于业务数据库；检查点独立使用可选的 `LANGGRAPH_PG_DSN`：

- 未设置、留空或仅包含空白：使用内存检查点，输出警告；进程重启后状态丢失。
- 填写 PostgreSQL 连接串：使用持久化检查点，可以与 `DATABASE_DSN` 填相同的值。
  连接失败会报错，不会自动退回内存。
- 每次打开内存 saver 都是新的存储；应用生命周期在当前进程内复用同一个 saver。

数据库初始化（先确保目标数据库已存在）：

```powershell
uv run alembic upgrade head
# Only needed when LANGGRAPH_PG_DSN is configured.
uv run python -m backend.scripts.init_checkpoints
```

检查点脚本在内存模式下会提示并跳过；PostgreSQL 模式仍由该脚本显式建表或升级表结构。
检查点已接入应用生命周期和旅行主图。CLI 已用模拟 Agent 验证新图/saver 实例
从真实 PostgreSQL checkpoint 恢复到确认并保存；真实模型/高德全流程和进程崩溃恢复仍待验证。

修改 `.env` 后重启后端。访问 `/health/db` 会执行 `SELECT 1`：

- 200：`{"status":"ok","database":"postgresql"}`
- 503：数据库未配置或连接不可用；响应不包含连接密码。

`/health` 仅检查 API 进程；`/health/db` 检查数据库连通性，不检查业务表是否齐全。
Alembic 自动生成迁移只检查已注册的业务模型，避免删除 checkpoint 表。
新增模型后需在 `backend/app/models/__init__.py` 导入；迁移环境统一加载该包，
生成并人工检查迁移文件后再应用；
删除业务表需要编写显式迁移。

```powershell
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run pytest backend/tests
```

业务模型的真实 PostgreSQL 集成测试位于 `backend/tests/db/test_business_models.py`。
设置 `TRAVELBUDDY_TEST_DATABASE_DSN` 指向已迁移的 PostgreSQL 测试库后运行；未设置则跳过。
每个测试用外层事务回滚写入的业务记录，不调用模型、高德或 checkpoint 写入。
Save 集成测试位于 `backend/tests/db/test_save.py`，验证真实提交、并发、幂等与失败恢复；
它会创建临时用户和会话，并在结束时按生成的精确 ID 清理记录。两组都可用
`uv run pytest backend/tests/db -q` 运行。图流程测试使用模拟 Agent，不调用真实模型或高德。

开发计划见 [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)。当前已搭建最小后端与健康检查，尚未实现业务功能。

## 目录规划

目录职责、当前文件映射和后续模块规划见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

当前已建立完整模块目录骨架。新增 Python 包只含 `__init__.py`，前端、部署、评估和提示词目录用 `.gitkeep` 占位，业务实现待后续逐步补充。已有健康检查与 PostgreSQL 基础设施代码保留。
