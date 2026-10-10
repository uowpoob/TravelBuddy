# TravelBuddy · 你的专属旅行伙伴

> 从一个旅行想法，到一份可以查看、调整和保存的行程。

TravelBuddy 是一个基于大语言模型与多 Agent 协作的旅行规划应用。你可以用自然语言描述目的地、出行时间和旅行偏好，系统会通过多轮对话补全需求，结合高德地图的地点、天气与路线信息生成每日行程，并在确认后保存到个人旅行空间。

## 一、项目功能

| 功能 | 说明 |
| --- | --- |
| 旅行工作台 | 填写目的地、日期、天数、人数、交通方式和旅行想法，快速发起规划；查看近期会话与最新行程地图。 |
| 对话式需求澄清 | 支持从“想去北京玩几天”这样的简单想法开始，逐步补齐信息，记录偏好、必去地点与其他要求。 |
| 多 Agent 协作规划 | 分工完成地点调研、出行条件分析、每日路线安排与方案审核，生成包含地点、地址、停留时间、交通耗时和出行提示的方案。 |
| 方案调整与确认 | 可以继续提出“第二天下午换成室内活动”等修改要求，满意后确认并保存行程。 |
| 规划进度展示 | 自动更新各节点的执行状态，查看当前正在理解需求、调研地点、安排路线或审核方案。 |
| 会话与行程管理 | 查看历史对话、继续规划、重试失败步骤；查看已保存的行程版本，删除会话或指定行程版本。 |
| 地图与真实路线 | 按天查看地点分布，切换步行、骑行、驾车或公交方式，查询道路路线、距离与预计耗时。 |
| 用户账号 | 支持注册、登录、退出及账号信息查看，会话和行程按用户归属管理。 |

当前支持 **1–5 天的旅行规划**。预算和出发城市可以留空；填写预算时，需要明确总预算或人均预算。天气以查询结果覆盖的日期为准，未获取到的费用会显示为“尚未估算”。

## 二、项目结构

```text
TravelBuddy/
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── agents/             # 地点调研、出行分析、规划、审核四类 Agent
│   │   ├── api/                # 认证、会话、行程、地图及健康检查接口
│   │   ├── core/               # 应用配置、认证与运行时配置
│   │   ├── db/                 # 数据库连接与会话管理
│   │   ├── graph/              # LangGraph 主流程、状态与检查点
│   │   ├── integrations/       # 模型、高德 MCP 与路线接口集成
│   │   ├── models/             # 用户、会话与行程数据库模型
│   │   ├── prompts/            # 需求理解与各 Agent 提示词
│   │   ├── repositories/       # 数据访问层
│   │   ├── schemas/            # 请求、响应与结构化输出定义
│   │   └── services/           # 业务逻辑
│   ├── migrations/            # Alembic 数据库迁移
│   ├── scripts/               # 密钥初始化、检查点初始化与调试脚本
│   ├── tests/                 # 后端测试
│   ├── pic/                   # 项目展示截图
│   └── __main__.py            # 后端启动入口
├── frontend/                  # React 前端
│   ├── src/
│   │   ├── api/               # 后端接口调用
│   │   ├── app/               # 应用入口与路由
│   │   ├── components/        # 布局与公共组件
│   │   ├── features/          # 认证、工作台、会话、行程与地图页面
│   │   ├── styles/            # 页面样式
│   │   ├── types/             # TypeScript 类型定义
│   │   ├── utils/             # 通用工具
│   │   └── test/              # 前端测试
│   └── public/                # 静态资源
├── deploy/                    # Dockerfile、Nginx 配置与部署说明
├── docs/                      # 架构、接口与开发文档
├── mcp_server/                # 预留的对外 MCP 服务目录
├── evals/                     # 预留的评测目录
├── compose.yaml               # Docker Compose 服务编排
├── .env.example               # 本地开发配置模板
├── pyproject.toml             # Python 依赖与工具配置
└── uv.lock                    # Python 依赖锁文件
```

后端通过高德远程 MCP 服务调用地图工具，当前无需启动 `mcp_server/`。更详细的模块说明见 [架构文档](docs/ARCHITECTURE.md)。

## 三、主要技术

| 层次 | 技术 | 用途 |
| --- | --- | --- |
| 前端 | React、TypeScript、Vite | 页面交互、类型约束与前端开发构建。 |
| 路由与界面 | React Router、Lucide React、CSS | 页面导航、图标与界面样式。 |
| 后端 | Python、FastAPI、Uvicorn | 提供异步业务 API 与自动生成的接口文档。 |
| AI 工作流 | LangChain、LangGraph、DeepSeek | 模型调用、工具使用、多 Agent 协作与可暂停恢复的规划流程。 |
| 数据校验 | Pydantic、Pydantic Settings | 校验业务数据、模型结构化输出与环境配置。 |
| 地图服务 | 高德 MCP、Web 服务 API、JS API 2.0 | 地点搜索、天气分析、交通路线查询与地图展示。 |
| 数据存储 | PostgreSQL、SQLAlchemy、Alembic | 保存账号、会话、行程版本并管理数据库迁移。 |
| 状态持久化 | LangGraph Checkpoint PostgreSQL | 保存规划状态，支持跨请求与重启后的会话恢复。 |
| 缓存 | Redis | 缓存高德 MCP 工具列表与只读查询结果。 |
| 身份认证 | JWT、密码加盐哈希 | 用户登录认证与接口访问控制。 |
| 工程与部署 | uv、pytest、Ruff、Vitest、Docker Compose、Nginx | 依赖管理、测试检查、容器部署与反向代理。 |

规划流程由 LangGraph 编排，四个专业 Agent 各自负责一个环节：

| Agent | 职责 |
| --- | --- |
| Researcher | 查询并筛选景点、餐厅、酒店等真实候选地点。 |
| Context Analyst | 查询天气，整理出行条件与建议。 |
| Planner | 结合候选地点、交通路线和用户偏好安排每日行程。 |
| Reviewer | 根据需求与已有证据审核方案，提出修改意见或需要用户补充的问题。 |

```mermaid
flowchart TD
    A[用户输入旅行想法] --> B[理解需求]
    B --> C{信息是否完整}
    C -->|否| D[向用户澄清]
    D --> B
    C -->|是| E[地点调研]
    C -->|是| F[出行条件分析]
    E --> G[行程规划]
    F --> G
    G --> H[方案审核]
    H -->|需要修订| G
    H -->|需要补充信息| D
    H -->|通过| I[用户确认]
    I -->|提出修改| B
    I -->|确认| J[保存行程版本]
```

自动审核修订最多进行一轮，仍有问题时进入用户澄清。用户也可以在确认阶段继续提出修改要求。

## 四、项目展示

以下截图展示了从登录、发起规划到确认方案和查看路线的使用过程。

### 登录与注册

进入个人旅行空间，管理自己的旅行会话与行程。

![TravelBuddy 登录页面](backend/pic/img.png)

### 旅行工作台

填写旅行想法并开始规划，也可以继续最近的会话、预览已保存行程的地点分布。

![旅行工作台](backend/pic/img_5.png)

### 旅行会话与规划进度

通过对话补充需求，查看各规划节点的执行状态。

![旅行会话与规划进度](backend/pic/img_1.png)

### 每日行程预览

按天展示地点、地址、停留时间和交通安排。图中为北京三日城市漫步方案。

![每日行程预览](backend/pic/img_2.png)

### 方案确认与调整

查看费用信息和行程提醒，确认保存或继续输入修改要求。

![方案确认与调整](backend/pic/img_3.png)

### 地图与路线

切换日期和交通方式，在地图上查看地点顺序与高德返回的道路路线。

![地图与路线](backend/pic/img_4.png)

## 五、快速开始

### 方式一：Docker 启动

准备好 Docker Engine / Docker Desktop 和 Docker Compose v2，下载项目后进入根目录。

**1. 创建配置文件**

```bash
cp deploy/.env.example deploy/.env
```

Windows PowerShell 使用 `Copy-Item deploy/.env.example deploy/.env`。已有配置时直接编辑现有文件。

**2. 编辑 `deploy/.env`**

| 配置项 | 说明 |
| --- | --- |
| `POSTGRES_PASSWORD` | 数据库密码，使用至少 32 个字符的随机十六进制值。 |
| `AUTH_SECRET_KEY` | JWT 签名密钥，使用独立生成的至少 32 字节随机值。 |
| `DEEPSEEK_API_KEY` | 模型服务 API Key。 |
| `DEEPSEEK_BASE_URL` | 模型供应商提供的 API 地址。 |
| `DEEPSEEK_MODEL` | 供应商支持的模型 ID，需支持工具调用；项目使用非思考模式。 |
| `GD_API_KEY` | 高德 Web 服务 Key，用于后端地点、天气与路线查询。 |
| `GD_JSAPI_KEY` | 高德 Web 端 JS API Key，用于前端地图。 |
| `GD_JSAPI_SECURITY_CODE` | 与 JS API Key 配对的安全密钥。 |

可以分别执行两次 `python -c "import secrets; print(secrets.token_hex(32))"`，生成数据库密码和 JWT 密钥并填入配置文件。

**3. 构建并启动**

```bash
docker compose --env-file deploy/.env config --quiet
docker compose --env-file deploy/.env up -d --build
docker compose --env-file deploy/.env ps -a
```

首次启动会安装依赖，启动 PostgreSQL 和 Redis，自动完成业务表迁移与检查点初始化，再启动后端和网页。`migrate` 服务正常退出状态为 `Exited (0)`。

打开 [http://127.0.0.1:8080](http://127.0.0.1:8080)，注册账号后即可开始使用。云服务器部署和排错步骤见 [部署说明](deploy/README.md)。

### 方式二：本地开发

准备 Python 3.13+、uv、Node.js 22.12+ 与 npm，以及可连接的 PostgreSQL 数据库。Redis 用于查询缓存，可以选择启用。

**1. 安装依赖并创建配置**

在项目根目录运行：

```bash
uv sync --locked
cp .env.example .env
```

Windows PowerShell 使用 `Copy-Item .env.example .env`。已有 `.env` 时直接编辑。

填写上表中的模型与高德配置，并配置数据库：

```dotenv
DATABASE_DSN=postgresql://travelbuddy:YOUR_PASSWORD@127.0.0.1:5432/travelbuddy
LANGGRAPH_PG_DSN=postgresql://travelbuddy:YOUR_PASSWORD@127.0.0.1:5432/travelbuddy
REDIS_URL=redis://127.0.0.1:6379/0
```

先在 PostgreSQL 中创建对应账号和 `travelbuddy` 数据库，再替换连接串中的账号、密码与地址；URI 密码中的特殊字符需进行 URL 编码。`LANGGRAPH_PG_DSN` 可以与业务数据库使用相同连接串，留空时使用内存检查点，后端重启后无法恢复规划状态。不使用 Redis 时，将 `REDIS_URL` 留空或设置 `GD_MCP_CACHE_ENABLED=false`。

**2. 初始化密钥与数据库**

```bash
uv run python -m backend.scripts.init_auth
uv run alembic upgrade head
uv run python -m backend.scripts.init_checkpoints
```

密钥初始化脚本会生成 `AUTH_SECRET_KEY` 并写入根目录 `.env`，已有有效密钥会保留；检查点初始化脚本在内存模式下会自动跳过。

**3. 启动后端**

```bash
uv run python -m backend --reload
```

后端默认运行在 `127.0.0.1:8000`，可访问 [接口文档](http://127.0.0.1:8000/docs)、[服务健康检查](http://127.0.0.1:8000/health) 和 [数据库健康检查](http://127.0.0.1:8000/health/db)。

**4. 启动前端**

打开另一个终端，运行：

```bash
cd frontend
npm ci
npm run dev
```

打开 [http://127.0.0.1:3000](http://127.0.0.1:3000)。前端开发服务器默认将 `/api` 代理到 `http://127.0.0.1:8000`；需要修改后端地址时，可参考 `frontend/.env.example`，在 `frontend/.env.local` 中设置 `API_PROXY_TARGET`。

### 开始第一段旅程

注册并登录后，在旅行工作台填写需求，或新建旅行会话发送：

> 我想在 2027 年 1 月 1 日去北京玩 3 天，1 个人，喜欢城市漫步和胡同美食，主要骑共享单车，节奏轻松一些。

根据提示补充信息，等待生成方案；可以继续提出修改，或点击“确认并保存行程”。保存后，在“我的行程”查看详情，在“地图与路线”按天查询交通路线。
