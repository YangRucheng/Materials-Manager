# 电气车间备件管理系统后端

## Agent 数据库接口

Agent 可使用超级管理员账号密码直接读取或修改当前业务数据库，无需先换取 JWT：

```text
X-Agent-Username: admin
X-Agent-Password: <超级管理员密码>
```

- `GET /api/v1/agent/database/schema`：读取全库表、字段、主键和外键结构。
- `POST /api/v1/agent/database/execute`：执行任意单条参数化 SQL，包括 `CREATE`、`ALTER`、`DROP`、`TRUNCATE`、授权语句及数据读写操作。

请求示例：

```json
{
  "sql": "SELECT * FROM stock_material WHERE id = :id",
  "parameters": {"id": 1},
  "max_rows": 1000
}
```

接口不接受分号或 SQL 注释，但不限制语句类型、数据库对象或目标表。该接口等同于直接使用应用数据库账号，能够造成不可逆的数据或结构变更；应严格保护超级管理员密码，并由数据库账号自身的权限控制最终可执行范围。生产环境必须使用 HTTPS，避免请求头密码在传输过程中泄露。

## 图片一致性与悬空文件

上传接口会在 `file_object` 记录提交成功后才返回 201；提交失败时同步回收已写入的磁盘文件。业务关联表只保存 `file_id`，文件名固定为 `<file_id>.png`，前端按 ID 拼接 `/api/v1/files/images/{file_id}`。

- `GET /api/v1/files/images/orphans?older_than_hours=24`：超级管理员查看未引用记录、无记录磁盘文件及磁盘缺失记录。
- `DELETE /api/v1/files/images/orphans?older_than_hours=24`：删除未引用记录和无记录磁盘文件；默认 24 小时保护期，避免误删刚上传但尚未绑定的图片。

数据库结构以最新版 `../example/database/init.sql` 为准，业务服务不会在运行时修改数据库结构。

FastAPI + SQLAlchemy 2.x async + MySQL 8.0，按 `docs/development-plan.md` 实现。

## 本地启动

要求 Python 3.12 和 MySQL 8.0：

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
copy ..\example\backend.env.example .env
mysql -h <数据库地址> -u <用户名> -p <数据库名> < ../example/database/init.sql
mkdir data\template
copy ..\example\template\*.json data\template\
.venv/Scripts/uvicorn app.main:app --reload
```

空数据库初始化通过 `../example/database/init.sql` 完成；`/health` 仅检查数据库连接。已有数据库的结构调整通过 Agent 超级管理员数据库接口执行。接口文档位于 `http://localhost:8000/api/docs`。初始账号为 `admin`、`warehouse`、`purchase`、`readonly`，初始密码均为 `123456`。

## 验证与契约

```bash
ruff check app tests
mypy app
pytest
python scripts/export_openapi.py
```

生产部署前必须修改 `APP_JWT_SECRET`。图片位于 `backend/data/uploads/`，应与 MySQL 使用相同备份周期。

运行日志默认写入 `backend/data/logs/spare-parts-api.log`。日志每天轮转，历史文件按
`YYYY-MM` 目录归档并保留 90 天；可通过 `APP_LOG_DIR` 和 `APP_LOG_BACKUP_COUNT` 调整。
控制台默认输出 ANSI 颜色，设置 `NO_COLOR=1` 可关闭。请求日志依次采用
`EO-Connecting-IP`、`X-Real-IP`、`X-Forwarded-For` 中的有效 IP；部署时应由可信反向代理覆盖这些请求头。
