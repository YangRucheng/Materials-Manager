import os
from importlib import import_module
from pathlib import Path

import yaml

os.environ.setdefault("APP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

app = import_module("app.main").app


target = Path(__file__).resolve().parents[2] / "docs" / "openapi.yaml"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False),
    encoding="utf-8",
)
print(target)
