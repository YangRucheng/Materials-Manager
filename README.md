# Materials Manager

电气车间二级库和申购管理系统。后端使用 FastAPI + MySQL，前端使用 Vue 3 + Naive UI。

## Docker 部署

项目不部署 MySQL 容器，必须连接已有的 MySQL 8.0 服务。

1. 在 MySQL 中创建数据库和账号。
2. 复制 `.env.example` 为 `.env`，修改 `APP_DATABASE_URL` 和 `APP_JWT_SECRET`。
3. 拉取并启动服务：

```bash
docker login docker.io
docker compose pull
docker compose up -d
```

默认访问地址：

- 前端：`http://localhost:8080`
- 后端接口文档：`http://localhost:8000/api/docs`

如果 MySQL 运行在 Docker 宿主机上，Windows/macOS 可以在连接串中使用 `host.docker.internal`；远程 MySQL 请填写其内网域名或 IP。密码中的 `@`、`:`、`/` 等字符必须进行 URL 编码。

首次启动会自动执行 Alembic 迁移并写入演示账号。生产使用前请修改初始密码及 JWT 密钥。上传图片保存在 Compose 的 `uploads` 数据卷中。

## Docker Hub 镜像

GitHub Actions 在推送 `main`、推送 `v*` 标签或手工触发时，将两个镜像推送到同一个 Docker Hub 仓库：

- `docker.io/yangrucheng/materials-manager:backend`
- `docker.io/yangrucheng/materials-manager:frontend`

仓库需要配置以下 GitHub Actions Secrets：

- `CCR_USERNAME`：Docker Hub 登录用户名（沿用原 Secret 名称）
- `CCR_PASSWORD`：Docker Hub 登录密码或访问令牌（沿用原 Secret 名称）

当前仓库已配置这两个 Secret。Docker Hub 账号 `yangrucheng` 下需要存在 `materials-manager` 镜像仓库，并允许该账号推送。

`main` 分支更新固定标签 `backend`、`frontend`；每次构建还会推送 `backend-sha-<commit>`、`frontend-sha-<commit>`，版本标签则生成 `backend-v*`、`frontend-v*`。

## 本地开发与验证

后端和前端的详细启动说明分别见 [backend/README.md](backend/README.md) 和 [frontend/README.md](frontend/README.md)。
