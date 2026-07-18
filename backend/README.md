# 电气车间备件管理系统后端

FastAPI + SQLAlchemy 2.x async + MySQL 8.0，按 `docs/development-plan.md` 实现。

## 本地启动

要求 Python 3.12 和 MySQL 8.0：

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
copy .env.example .env
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.seed
.venv/Scripts/uvicorn app.main:app --reload
```

接口文档位于 `http://localhost:8000/api/docs`。种子账号为 `admin`、`warehouse`、`purchase`、`readonly`，初始密码均为 `123456`。

## 验证与契约

```bash
ruff check app tests
mypy app
pytest
python scripts/export_openapi.py
```

生产部署前必须修改 `APP_JWT_SECRET`。图片位于 `backend/data/uploads/`，应与 MySQL 使用相同备份周期。
