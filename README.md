# Materials Manager

电气车间二级库和申购管理系统。后端使用 FastAPI + MySQL，前端使用 Vue 3 + Naive UI。

## Docker 部署

项目不部署 MySQL 容器，必须连接已有的 MySQL 8.0 服务。

1. 在 MySQL 中创建空数据库，并将 [database/init.sql](database/init.sql) 导入该数据库。
2. 确认 MySQL 服务已加入外部 Docker 网络 `1panel-network`。
3. 复制 `.env.example` 为 `.env`，修改 `APP_DATABASE_URL` 和 `APP_JWT_SECRET`。连接串中的主机名应填写 `1panel-network` 内可访问的 MySQL 容器名。
4. 拉取并启动服务：

```bash
docker login docker.io
docker compose pull
docker compose up -d
```

默认访问地址：

- 前端：`http://localhost:8080`
- 后端接口文档：`http://localhost:8000/api/docs`

Compose 会直接使用 1Panel 已有的外部网络 `1panel-network`，不会创建或管理 MySQL 容器。远程 MySQL 也可填写其内网域名或 IP。密码中的 `@`、`:`、`/` 等字符必须进行 URL 编码。

后端容器不会自动建表、迁移或写入种子数据，数据库初始化与业务服务启动完全分离。初始化 SQL 会创建四个账号：`admin`、`warehouse`、`purchase`、`readonly`，初始密码均为 `123456`。首次登录后请立即修改密码，并在生产使用前修改 JWT 密钥。上传图片保存在 Compose 的 `uploads` 数据卷中。

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
