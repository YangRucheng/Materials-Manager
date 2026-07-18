# 电气车间备件管理系统后端

FastAPI + SQLAlchemy 2.x async + MySQL 8.0，按 `docs/development-plan.md` 实现。

## 本地启动

要求 Python 3.12 和 MySQL 8.0：

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
copy .env.example .env
mysql -h <数据库地址> -u <用户名> -p <数据库名> < ../database/init.sql
.venv/Scripts/uvicorn app.main:app --reload
```

空数据库初始化通过项目根目录的 `database/init.sql` 完成；当前开发阶段不执行运行时迁移，结构变化后需要重建空库。Docker 容器会直接启动 API 服务，`/health` 仅通过只读元数据查询校验表结构，不会自动修改数据库。接口文档位于 `http://localhost:8000/api/docs`。初始账号为 `admin`、`warehouse`、`purchase`、`readonly`，初始密码均为 `123456`。

## 验证与契约

```bash
ruff check app tests
mypy app
pytest
python scripts/export_openapi.py
```

生产部署前必须修改 `APP_JWT_SECRET`。图片位于 `backend/data/uploads/`，应与 MySQL 使用相同备份周期。
