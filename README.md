# Materials Manager

电气车间二级库和申购管理系统。后端使用 FastAPI + MySQL，前端使用 Vue 3 + Naive UI。

## Docker 部署

项目不部署 MySQL 容器，必须连接已有的 MySQL 8.0 服务。

1. 在 MySQL 中创建数据库和账号。
2. 复制 `.env.example` 为 `.env`，修改 `APP_DATABASE_URL` 和 `APP_JWT_SECRET`。
3. 拉取并启动服务：

```bash
docker login ccr.ccs.tencentyun.com
docker compose pull
docker compose up -d
```

默认访问地址：

- 前端：`http://localhost:8080`
- 后端接口文档：`http://localhost:8000/api/docs`

如果 MySQL 运行在 Docker 宿主机上，Windows/macOS 可以在连接串中使用 `host.docker.internal`；远程 MySQL 请填写其内网域名或 IP。密码中的 `@`、`:`、`/` 等字符必须进行 URL 编码。

首次启动会自动执行 Alembic 迁移并写入演示账号。生产使用前请修改初始密码及 JWT 密钥。上传图片保存在 Compose 的 `uploads` 数据卷中。

## 腾讯云 CCR 镜像

GitHub Actions 在推送 `main`、推送 `v*` 标签或手工触发时构建并推送：

- `ccr.ccs.tencentyun.com/yangrucheng/materials-manager-backend`
- `ccr.ccs.tencentyun.com/yangrucheng/materials-manager-frontend`

仓库需要配置以下 GitHub Actions Secrets：

- `CCR_USERNAME`：腾讯云 CCR 登录用户名
- `CCR_PASSWORD`：腾讯云 CCR 登录密码

当前仓库已配置这两个 Secret。腾讯云命名空间 `yangrucheng` 下需要允许创建或预先创建上述两个镜像仓库。

每次构建会推送 `latest`（仅 `main`）、`sha-<commit>` 和对应的 `v*` 标签。

## 本地开发与验证

后端和前端的详细启动说明分别见 [backend/README.md](backend/README.md) 和 [frontend/README.md](frontend/README.md)。
