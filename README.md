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
FastAPI 启动时只保存客户端配置，不访问高德。

在项目根目录执行：

```powershell
# List all tools, including their descriptions and JSON schemas.
uv run python -m backend.scripts.amap_mcp list

# Example: use this only if list returns maps_weather with a city parameter.
uv run python -m backend.scripts.amap_mcp call maps_weather --arguments '{"city":"杭州"}'

# Alternatively, read a JSON object from a UTF-8 file.
uv run python -m backend.scripts.amap_mcp call maps_weather --arguments-file ./weather-arguments.json
```

工具名称与参数以 `list` 返回的实际 schema 为准；不写参数时发送空 JSON 对象。
`--arguments` 与 `--arguments-file` 只能选择一个。
命令不依赖数据库、DeepSeek 或正在运行的 FastAPI。
结果输出保留原始 MCP 的 `content`、`structuredContent` 和 `isError`，
工具执行失败或连接失败时返回非零退出码。当前未运行测试或真实高德调用。

Python 调用入口为 `AmapMCPClient()` 的 `await client.list_tools()` 和
`await client.call_tool(name, arguments)`；返回 SDK 原生类型，工具失败检查
`result.is_error`。FastAPI 路由可通过 `get_amap_mcp_client` 依赖获取同一客户端配置；
未配置 Key 时该依赖返回 503。当前尚未将工具绑定到 Agent 或实现前端业务接口。

## PostgreSQL

业务数据使用 SQLAlchemy 访问，业务表变更使用 Alembic 管理；LangGraph 检查点由
`langgraph-checkpoint-postgres` 单独管理。当前还没有业务表或业务迁移版本。

本地 `.env` 的 `DATABASE_DSN` 指向独立的 `travelbuddy` 数据库。
连接账号可复用现有本地 PostgreSQL 账号，但不要指向其他项目的数据库。
新环境可复制 `.env.example` 为 `.env` 后填写连接信息；不要覆盖已有 `.env`。
`python -m backend` 已配置 Windows 下 psycopg 所需的 SelectorEventLoop。
此配置既支持 PostgreSQL URI，也支持 psycopg 的 `host=... dbname=...` 格式。

`DATABASE_DSN` 用于业务数据库；检查点独立使用可选的 `LANGGRAPH_PG_DSN`：

- 未设置、留空或仅包含空白：使用内存检查点，输出警告；进程重启后状态丢失。
- 填写 PostgreSQL 连接串：使用持久化检查点，可以与 `DATABASE_DSN` 填相同的值。
  连接失败会报错，不会自动退回内存。
- 每次打开内存 saver 都是新的存储；后续接入 Graph 时应在应用生命周期中复用同一个 saver。

数据库初始化（先确保目标数据库已存在）：

```powershell
uv run alembic upgrade head
# Only needed when LANGGRAPH_PG_DSN is configured.
uv run python -m backend.scripts.init_checkpoints
```

检查点脚本在内存模式下会提示并跳过；PostgreSQL 模式仍由该脚本显式建表或升级表结构。
当前检查点封装尚未接入应用生命周期和业务 Graph。

修改 `.env` 后重启后端。访问 `/health/db` 会执行 `SELECT 1`：

- 200：`{"status":"ok","database":"postgresql"}`
- 503：数据库未配置或连接不可用；响应不包含连接密码。

`/health` 仅检查 API 进程；`/health/db` 检查数据库连通性，不检查业务表是否齐全。
Alembic 自动生成迁移只检查已注册的业务模型，避免删除 checkpoint 表。
新增模型后需在 `backend/migrations/env.py` 导入，生成并人工检查迁移文件后再应用；
删除业务表需要编写显式迁移。

```powershell
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run pytest backend/tests
```

开发计划见 [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)。当前已搭建最小后端与健康检查，尚未实现业务功能。

## 目录规划

目录职责、当前文件映射和后续模块规划见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

当前已建立完整模块目录骨架。新增 Python 包只含 `__init__.py`，前端、部署、评估和提示词目录用 `.gitkeep` 占位，业务实现待后续逐步补充。已有健康检查与 PostgreSQL 基础设施代码保留。
