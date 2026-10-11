# TravelBuddy 部署

同一份代码支持本地 Docker 部署和云服务器部署。`deploy/`、Dockerfile、Nginx 配置、根目录 `compose.yaml` 和 `.dockerignore` 应提交到 Git；真实 `deploy/.env`、备份和数据库文件不提交。

## 首次启动

需要 Docker Engine / Desktop 和 Docker Compose v2。在项目根目录执行：

```bash
cp deploy/.env.example deploy/.env
```

Windows PowerShell 对应命令：`Copy-Item deploy/.env.example deploy/.env`。

编辑 `deploy/.env`：

- `POSTGRES_PASSWORD`：自行生成的随机十六进制密码，至少 32 个字符；这里使用十六进制是为了避免数据库 URI 特殊字符转义。
- `AUTH_SECRET_KEY`：独立随机密钥，至少 32 字节，不使用模型 Key 替代。
- `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`：填自己模型供应商的配置，模型名称与供应商匹配。
- `GD_API_KEY`：高德 Web 服务 Key。
- `GD_JSAPI_KEY`、`GD_JSAPI_SECURITY_CODE`：高德 Web 端 JS Key 及其配对安全密钥。

Ubuntu 可分别执行两次 `openssl rand -hex 32`，生成数据库密码和 JWT 密钥。在 PowerShell 可用 `python -c "import secrets; print(secrets.token_hex(32))"`，同样执行两次。密钥只粘贴到本机或服务器的配置文件。

```bash
docker compose --env-file deploy/.env config --quiet
docker compose --env-file deploy/.env up -d --build
docker compose --env-file deploy/.env ps -a
```

本地打开 <http://127.0.0.1:8080>。初次启动会拉取镜像、安装锁定依赖、创建 PostgreSQL、执行业务迁移和 checkpoint 初始化，然后启动 API 与网页。`migrate` 正常状态为 `Exited (0)`，其他服务应为运行中且健康。

Compose 会自动把数据库和 Redis 地址设为容器服务名，不读取根目录本地开发 `.env`。数据库与 checkpoint 共用本部署的 PostgreSQL，并保存在独立 Docker 命名卷中。不会迁入原本机数据，也不会向宿主机发布 5432、6379、8000 端口。

前端正式构建使用同源 `/api`，由 Nginx 转发。网页路由刷新回退至 `index.html`；规划请求代理超时为 330 秒。服务默认自动重启。Redis 仅作缓存，限制内存 128 MB，缓存可重建。

## 阿里云 Ubuntu + Docker 应用镜像

1. 通过阿里云控制台远程连接或 SSH 登录服务器，确认 `docker version`、`docker compose version` 可用。如果当前用户无 Docker 权限，命令前加 `sudo`。
2. 把已提交的项目从 GitHub 克隆到服务器（不要把本地 `.venv`、`node_modules`、真实 `.env` 上传到 GitHub）。也可以直接上传源码包。进入项目根目录。
3. 按上面的步骤创建服务器专用 `deploy/.env`，模型与高德 Key 可使用站点所有者自己的配置。
4. 没有域名、先通过公网 IP 演示：设置 `WEB_BIND_ADDRESS=0.0.0.0`、`WEB_PORT=80`。确保宿主机 80 端口未被其他服务使用。
5. 在该实例的安全组或防火墙中允许 TCP 80；SSH 22 仅对需要管理服务器的来源开放。数据库和 Redis 无需开放。
6. 启动后访问 `http://服务器公网IP`。这是临时 HTTP 演示入口；使用真实账号对外分享时，配置域名、证书和 HTTPS。

如果已经有宿主机 Nginx 或其他 HTTPS 网关，保持 `WEB_BIND_ADDRESS=127.0.0.1`、`WEB_PORT=8080`，由网关转发到 `http://127.0.0.1:8080`。网关同样需要把读取超时设为至少 330 秒，并传递 Host 和转发头。HTTPS 在网关终止，证书不放进公开仓库。

高德控制台的 Key 限制需要与部署环境一致（网页域名、服务器出口 IP 等）。如果地域网络不能访问镜像仓库或供应商接口，先确认具体失败地址，再配置可信镜像源或将本机构建的镜像通过 `docker save` / `docker load` 搬到服务器。

首次安装可以直接在服务器构建，不要求先上传 Docker Hub。国内实例可能无法直接拉取 Docker Hub 镜像；本机镜像搬运步骤也可在确定服务器 CPU 架构后使用。

## 验收与排错

```bash
docker compose --env-file deploy/.env logs --tail=100 migrate
docker compose --env-file deploy/.env logs --tail=100 backend
docker compose --env-file deploy/.env exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/db').status)"
```

日志和配置可能包含业务内容；公开提问前先脱敏。不要把 `docker compose config` 的完整结果公开粘贴；检查配置使用 `config --quiet`。

网页验收：注册 → 登录 → 新建会话 → 发送不完整需求 → 补齐澄清 → 查看方案 → 修改 → 确认保存 → 查看行程和地图 → 重启后重新打开会话。`/health/db` 成功只代表数据库可访问，模型和高德是否可用仍需实际规划验证。

## 更新与备份

更新前备份数据库。在 Ubuntu：

```bash
mkdir -p .local/backups
docker compose --env-file deploy/.env exec -T db pg_dump -U travelbuddy travelbuddy > .local/backups/travelbuddy.sql
```

定期将备份复制到服务器之外。备份包含用户和对话数据，不提交 Git。

同步代码后，在维护窗口执行：

```bash
docker compose --env-file deploy/.env build backend frontend
docker compose --env-file deploy/.env stop frontend backend
docker compose --env-file deploy/.env run --rm migrate
docker compose --env-file deploy/.env up -d --no-build
```

确认迁移返回成功再执行最后一步。更改 Key 后使用 `up -d --force-recreate backend` 更新进程环境（只用 `restart` 不会加载新环境变量）。

临时停止：`docker compose --env-file deploy/.env stop`。`down` 保留数据库命名卷；不要使用 `down -v`，它会删除数据库卷。首次初始化之后，修改 `POSTGRES_PASSWORD` 不会自动修改数据库中的密码，已有数据库需要另行协调密码变更。

## 参考

- [Docker Compose 服务启动顺序](https://docs.docker.com/compose/how-tos/startup-order/)
- [uv Docker 集成](https://docs.astral.sh/uv/guides/integration/docker/)
