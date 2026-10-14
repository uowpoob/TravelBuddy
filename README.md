<h1 align="center">🧭 TravelBuddy</h1>

<p align="center"><strong>你的专属旅行伙伴 · AI 旅行规划助手</strong></p>
<p align="center">从一个旅行想法，到一份可以查看、调整和保存的行程。</p>

<p align="center">
  <code>React</code> · <code>TypeScript</code> · <code>FastAPI</code> · <code>LangGraph</code> · <code>DeepSeek</code> · <code>高德地图</code>
</p>

<p align="center">
  <a href="#features">✨ 项目功能</a> ·
  <a href="#structure">📦 项目结构</a> ·
  <a href="#technology">🛠️ 主要技术</a> ·
  <a href="#showcase">📸 项目展示</a> ·
  <a href="#roadmap">💡 待优化方向</a> ·
  <a href="#quick-start">🚀 快速开始</a>
</p>

---

TravelBuddy 是一个基于大语言模型与多 Agent 协作的旅行规划应用。你可以用自然语言描述目的地、出行时间和旅行偏好，系统会通过多轮对话补全需求，结合高德地图的地点、天气与路线信息生成每日行程，并在确认后保存到个人旅行空间。

<a id="features"></a>

## ✨ 项目功能

| 功能 | 说明 |
| --- | --- |
| 🏡 **旅行工作台** | 填写目的地、日期、天数、人数、交通方式和旅行想法，快速发起规划；查看近期会话与最新行程地图。 |
| 💬 **对话式需求澄清** | 支持从“想去北京玩几天”这样的简单想法开始，逐步补齐信息，记录偏好、必去地点与其他要求。 |
| 🤝 **多 Agent 协作规划** | 分工完成地点调研、出行条件分析、每日路线安排与方案审核，生成包含地点、地址、停留时间、交通耗时和出行提示的方案。 |
| ✏️ **方案调整与确认** | 可以继续提出“第二天下午换成室内活动”等修改要求，满意后确认并保存行程。 |
| ⏳ **规划进度展示** | 自动更新各节点的执行状态，查看当前正在理解需求、调研地点、安排路线或审核方案。 |
| 🗂️ **会话与行程管理** | 查看历史对话、继续规划、重试失败步骤；查看已保存的行程版本，删除会话或指定行程版本。 |
| 🗺️ **地图与真实路线** | 按天查看地点分布，切换步行、骑行、驾车或公交方式，查询道路路线、距离与预计耗时。 |
| 🔐 **用户账号** | 支持注册、登录、退出及账号信息查看，会话和行程按用户归属管理。 |

当前支持 **1–5 天的旅行规划**。预算和出发城市可以留空；填写预算时，需要明确总预算或人均预算。天气以查询结果覆盖的日期为准，未获取到的费用会显示为“尚未估算”。

---

<a id="structure"></a>

## 📦 项目结构

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

---

<a id="technology"></a>

## 🛠️ 主要技术

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
| 缓存 | Redis | 缓存高德 MCP 工具列表、只读查询结果及相同需求的 Researcher 候选地点。 |
| 身份认证 | JWT、密码加盐哈希 | 用户登录认证与接口访问控制。 |
| 工程与部署 | uv、pytest、Ruff、Vitest、Docker Compose、Nginx | 依赖管理、测试检查、容器部署与反向代理。 |

### 🤝 Agent 分工


规划流程由 LangGraph 编排，四个专业 Agent 各自负责一个环节：

| Agent | 职责 |
| --- | --- |
| 🔍 Researcher | 查询并筛选景点、餐厅、酒店等真实候选地点。 |
| ☁️ Context Analyst | 查询天气，整理出行条件与建议。 |
| 🗓️ Planner | 结合候选地点、交通路线和用户偏好安排每日行程。 |
| ✅ Reviewer | 根据需求与已有证据审核方案，提出修改意见或需要用户补充的问题。 |

### 🔄 当前规划流程

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

---

<a id="showcase"></a>

## 📸 项目展示

以下截图展示了从登录、发起规划到确认方案和查看路线的使用过程。

### 🔐 登录与注册

进入个人旅行空间，管理自己的旅行会话与行程。

<p align="center">
  <img src="backend/pic/img.png" width="92%" alt="TravelBuddy 登录页面" />
  <br /><em>世界很大，下一程一起出发。</em>
</p>

### 🏡 旅行工作台

填写旅行想法并开始规划，也可以继续最近的会话、预览已保存行程的地点分布。

<p align="center">
  <img src="backend/pic/img_5.png" width="92%" alt="旅行工作台" />
  <br /><em>从旅行想法开始，连接会话、规划与地图。</em>
</p>

### 💬 旅行会话与规划进度

通过对话补充需求，查看各规划节点的执行状态。

<p align="center">
  <img src="backend/pic/img_1.png" width="92%" alt="旅行会话与规划进度" />
  <br /><em>多轮补充需求，查看每个节点的执行状态。</em>
</p>

### 🗓️ 每日行程预览

按天展示地点、地址、停留时间和交通安排。图中为北京三日城市漫步方案。

<p align="center">
  <img src="backend/pic/img_2.png" width="92%" alt="每日行程预览" />
  <br /><em>按天展开行程，查看地点、停留时间与交通安排。</em>
</p>

### ✏️ 方案确认与调整

查看费用信息和行程提醒，确认保存或继续输入修改要求。

<p align="center">
  <img src="backend/pic/img_3.png" width="92%" alt="方案确认与调整" />
  <br /><em>满意就保存，有新想法就继续调整。</em>
</p>

### 🗺️ 地图与路线

切换日期和交通方式，在地图上查看地点顺序与高德返回的道路路线。

<p align="center">
  <img src="backend/pic/img_4.png" width="92%" alt="地图与路线" />
  <br /><em>把每日安排放到地图上，查看真实道路路线。</em>
</p>

---

<a id="roadmap"></a>

## 💡 待优化方向

目前已完成从需求澄清到确认保存的核心流程。后续重点是提升长期偏好记忆、行程安排质量，以及用户在规划过程中的参与感。以下为规划中的优化项。

### 🧠 会话总结与用户偏好记忆

当前会话会保留历史消息与结构化旅行需求，需求理解主要参考近期对话。后续计划加入会话摘要和跨会话偏好记忆，让长期对话中的重要决定更容易被后续规划使用。

- [ ] **会话自动总结**：提炼已确认需求、方案修改、地点选择与待解决问题，减少长对话中的信息遗漏与上下文开销。
- [ ] **用户偏好沉淀**：总结旅行节奏、兴趣主题、饮食偏好、常用交通方式和预算习惯，供新的旅行规划参考。
- [ ] **偏好可查看与修改**：用户可以确认、纠正或删除已记住的偏好；区分长期习惯与本次旅行的临时要求。
- [ ] **记忆参与规划**：将会话摘要、用户偏好与本次需求一起交给 Planner，本次明确要求优先，减少重复询问。

### 🃏 地点卡片与分阶段用户交互

当前地点调研完成后会与出行分析结果汇合，直接进入 Planner。计划在地点搜索与行程规划之间增加用户选择环节，让用户先挑选想去的地点，再生成每日安排。

**目标体验：搜索地点 → 展示卡片 → 用户选择加入行程 → Planner 安排路线。**

- [ ] **搜索结果卡片化**：Researcher 查询后，前端展示景点、餐厅与酒店卡片，包含名称、地址、推荐理由及可用的地点信息。
- [ ] **选择加入行程**：支持“加入行程”“移除”“设为必去”，并提供“换一批”或继续搜索；已选地点与地图标记联动。
- [ ] **选择后继续规划**：用户点击“开始安排”，后端校验所选地点，将选择结果与出行条件交给 Planner；也可选择“帮我挑选”，由系统推荐。
- [ ] **分阶段暂停与恢复**：在地点选择阶段保存状态，离开页面后可以继续选择，已选结果在重试或修改时保留。
- [ ] **生成后局部调整**：按天或单个地点进行替换、增删和顺序调整，优先重算受影响的路线，并展示调整前后的差异。

```mermaid
flowchart TD
    A[理解需求与读取偏好] --> B[Researcher 搜索地点]
    A --> C[Context Analyst 分析出行条件]
    B --> D[前端展示地点卡片]
    D --> E{用户选择}
    E -->|换一批或补充搜索| B
    E -->|加入行程并确认| F[保存已选地点与必去要求]
    E -->|帮我挑选| F
    F --> G[Planner 结合选择与偏好安排每日行程]
    C --> G
    G --> H[审核与行程预览]
    H --> I{用户反馈}
    I -->|调整地点| D
    I -->|调整节奏或安排| G
    I -->|确认| J[保存行程并更新会话摘要]
```

*上图为后续交互方案，地点选择卡片和新增暂停阶段尚未实现。*

### 🗓️ 行程质量与规划体验

| 优化方向 | 后续目标 |
| --- | --- |
| 📍 **空间与时间安排** | 进一步结合地理位置、可用营业时间、停留时长与交通耗时，减少绕路，控制每日活动强度。 |
| 💰 **预算与信息完整性** | 细分交通、餐饮、住宿和门票费用，标明来源与待核实项，便于比较方案。 |
| ⚡ **响应速度与反馈** | 在现有缓存和进度展示基础上，优化查询复用与限流处理，逐步展示已完成的地点或行程结果。 |
| 🔎 **规划质量评估** | 建立典型旅行场景评测，关注偏好匹配、路线合理性、修改成功率与用户反馈。 |

---

<a id="quick-start"></a>

## 🚀 快速开始

### 🐳 方式一：Docker 启动

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

### 💻 方式二：本地开发

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

### 🎒 开始第一段旅程

注册并登录后，在旅行工作台填写需求，或新建旅行会话发送：

> 我想在 2027 年 1 月 1 日去北京玩 3 天，1 个人，喜欢城市漫步和胡同美食，主要骑共享单车，节奏轻松一些。

根据提示补充信息，等待生成方案；可以继续提出修改，或点击“确认并保存行程”。保存后，在“我的行程”查看详情，在“地图与路线”按天查询交通路线。

## 🧪 持续集成（CI）

[CI 工作流](.github/workflows/ci.yml) 在代码推送、PR 创建或更新时自动运行，也可以在 GitHub 的 **Actions → CI → Run workflow** 中手动触发。前后端分别运行，检查失败时可以打开对应任务查看日志。

| 任务 | 检查内容 |
| --- | --- |
| `Backend checks` | 使用 Python 3.13 和 uv 锁文件安装依赖，执行 Ruff、数据库迁移、检查点初始化及全部 pytest 测试。 |
| `Frontend checks` | 使用 Node.js 24 和 npm 锁文件安装依赖，执行 Vitest、TypeScript 检查和 Vite 生产构建。 |

后端任务会启动临时 PostgreSQL 17 和 Redis 7，并设置 `TRAVELBUDDY_TEST_DATABASE_DSN`、`TRAVELBUDDY_TEST_REDIS_URL`，让真实数据库和缓存测试参与检查。模型及高德响应由测试模拟，普通 CI 无需配置真实 API 密钥；任务结束后临时服务由 GitHub 清理。

提交前可以在项目根目录运行：

```bash
uv sync --locked --dev
uv run --locked ruff check backend
uv run --locked pytest -ra
```

在 `frontend` 目录运行：

```bash
npm ci
npm test
npm run build
```

本地未设置测试连接地址时，PostgreSQL 和 Redis 集成测试会跳过；如需运行，使用独立测试数据库，先配置 `DATABASE_DSN` 并执行 `uv run --locked alembic upgrade head`，再把同一地址设为 `TRAVELBUDDY_TEST_DATABASE_DSN`。设置 `TRAVELBUDDY_TEST_REDIS_URL` 可启用真实 Redis 测试。

若要要求 PR 检查通过后才能合并，在 GitHub 中为主分支 `master` 配置分支保护或 ruleset，将 `Backend checks` 和 `Frontend checks` 设为必需状态检查。当前工作流负责验证代码，不包含服务器部署。
