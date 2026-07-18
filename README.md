# 电气车间备件管理系统

用于管理电气车间二级库库存和物资申购流程，不记录物资价格或成本。

## 系统功能

- 二级库：物资档案、图片附件、入库、出库、库存余额和流水查询。
- 库存预警：设置最低库存和目标库存，低库存时生成申购计划。
- 申购计划：登记物资、计划数量、用途、项目和负责人，未编码物资可后续补充编码。
- 申购记录：计划编码后转为正式记录，按物资展平跟踪业务员、备注和到货进度。
- 流水修正：库存允许为负数，已产生的库存流水允许修改并自动重算后续库存。
- 简单角色：超级管理员、仓库管理员、申购管理员和只读角色。

## 部署组成

| 组件   | 说明                                                                                               |
| ------ | -------------------------------------------------------------------------------------------------- |
| 前端   | Vue 3 静态站点；镜像为 `docker.io/yangrucheng/materials-manager:frontend`，并将 `/api/` 转发到后端 |
| 后端   | FastAPI 服务；镜像为 `docker.io/yangrucheng/materials-manager:backend`                             |
| 数据库 | 已有的 MySQL 8.0 或更高版本，本项目不会启动 MySQL 容器                                             |
| 图片   | 保存在 Docker 卷 `materials-manager_uploads` 中                                                    |

仓库中的 `docker-compose.yml` 直接使用 Docker Hub 已构建镜像，不需要在部署服务器上编译前后端。

## 部署前准备

- Docker Engine 和 Docker Compose v2。
- 一个可用的 MySQL 8.0+ 数据库及应用账号。
- Docker 外部网络 `1panel-network`。1Panel 通常已创建该网络。
- 当前仓库中的 `docker-compose.yml`、`.env.example` 和 `database/init.sql`。

获取部署文件：

```bash
git clone https://github.com/YangRucheng/Materials-Manager.git
cd Materials-Manager
```

### 1. 准备 Docker 网络

确认网络存在：

```bash
docker network inspect 1panel-network
```

如果不是通过 1Panel 部署，可手工创建：

```bash
docker network create 1panel-network
```

MySQL 运行在 Docker 中时，也要加入该网络：

```bash
docker network connect 1panel-network <MySQL容器名>
```

### 2. 初始化数据库

先创建空数据库和应用账号，再将初始化脚本导入该数据库：

```bash
mysql -h <数据库地址> -P 3306 -u <数据库用户> -p <数据库名> < database/init.sql
```

也可以直接通过 1Panel 的数据库导入功能上传 `database/init.sql`。

初始化脚本会创建表、基础计量单位和初始登录账号，但不会创建数据库或 MySQL 账号。当前开发阶段不执行运行时迁移；数据库结构变化后，请删除并重建空库，再导入最新版 `database/init.sql`。

`database/init.sql` 仅用于初始化空数据库，不要将它作为已有生产数据库的升级脚本重复导入。

### 3. 配置运行参数

复制环境变量示例：

```bash
cp .env.example .env
```

至少修改以下两项：

```dotenv
APP_DATABASE_URL=mysql+asyncmy://用户名:密码@MySQL容器名:3306/数据库名?charset=utf8mb4
APP_JWT_SECRET=不少于32个随机字符
```

可使用以下命令生成 JWT 密钥：

```bash
openssl rand -hex 32
```

全部配置项：

| 配置项                     | 必填 | 默认值 | 说明                                                        |
| -------------------------- | ---- | ------ | ----------------------------------------------------------- |
| `APP_DATABASE_URL`         | 是   | 无     | 后端数据库连接串；容器内主机名应使用 MySQL 容器名或内网地址 |
| `APP_JWT_SECRET`           | 是   | 无     | 登录令牌签名密钥，至少 32 个随机字符                        |
| `APP_ACCESS_TOKEN_MINUTES` | 否   | `480`  | 登录令牌有效期，单位为分钟                                  |
| `FRONTEND_PORT`            | 否   | `8080` | 前端映射到宿主机的端口                                      |
| `BACKEND_PORT`             | 否   | `8000` | 后端映射到宿主机的端口                                      |

如果数据库密码包含 `@`、`:`、`/`、`#` 等字符，必须先进行 URL 编码。

### 4. 启动服务

```bash
docker compose pull
docker compose up -d
docker compose ps
```

正常情况下，`backend` 和 `frontend` 最终都应显示为 `healthy`。

### 5. 验证部署

```bash
curl http://127.0.0.1:8000/health
```

正常响应：

```json
{ "status": "ok", "database": "ok" }
```

默认访问地址：

- 系统页面：`http://服务器地址:8080`
- 接口文档：`http://服务器地址:8000/api/docs`

如果修改了 `FRONTEND_PORT` 或 `BACKEND_PORT`，请使用实际端口。

## 初始账号

| 用户名      | 角色       |
| ----------- | ---------- |
| `admin`     | 超级管理员 |
| `warehouse` | 仓库管理员 |
| `purchase`  | 申购管理员 |
| `readonly`  | 只读角色   |

初始密码均为 `123456`。首次部署后请立即由超级管理员修改所有初始密码。

## 日常运维

### 查看状态和日志

```bash
docker compose ps
docker compose logs --tail=200 backend
docker compose logs --tail=200 frontend
```

持续查看日志：

```bash
docker compose logs -f
```

### 升级

固定标签 `backend` 和 `frontend` 指向 `main` 分支最新构建。当前开发阶段以最新版 `database/init.sql` 为准；数据库结构变化后，应删除并重建空库，不能向已有数据库重复导入初始化脚本。

确认数据库结构与当前版本一致后执行：

```bash
docker compose pull
docker compose up -d --remove-orphans
docker compose ps
```

后端容器不执行数据库迁移，会直接启动 API。升级后应重新检查 `/health` 并完成一次登录验证。

### 停止服务

```bash
docker compose down
```

不要执行 `docker compose down -v`，否则会删除图片数据卷。

### 备份

必须同时备份：

1. MySQL 数据库。
2. Docker 卷 `materials-manager_uploads` 中的图片。

查看图片卷的实际位置：

```bash
docker volume inspect materials-manager_uploads
```

数据库和图片应使用相同的备份周期，并尽量在同一时间点完成备份。

## 常见故障

| 现象                                         | 优先检查                                                        |
| -------------------------------------------- | --------------------------------------------------------------- |
| 提示外部网络不存在                           | 执行 `docker network inspect 1panel-network`                    |
| 后端状态为 `unhealthy` 或 `/health` 返回 503 | 检查数据库连接串、MySQL 网络、账号权限以及初始化脚本是否已导入  |
| 前端出现 502                                 | 检查后端容器状态和 `docker compose logs backend`                |
| 登录提示用户名或密码错误                     | 确认初始化脚本导入成功，并检查账号是否被停用或密码已被修改      |
| 接口返回表不存在                             | 初始化脚本未导入目标数据库，或连接串指向了错误数据库            |
| 图片无法上传或显示                           | 检查 `materials-manager_uploads` 卷是否存在以及 Docker 存储空间 |

## 上线安全检查

- 不要提交包含真实密码或密钥的 `.env` 文件。
- 修改全部初始账号密码和 `APP_JWT_SECRET`。
- 通过 1Panel 或其他反向代理启用 HTTPS。
- 除非确有需要，不要将后端端口直接暴露到公网。
- 定期验证数据库和图片备份可以恢复。
