from pathlib import Path

import pytest

from app.core.config import Settings, settings
from app.core.errors import AppError
from app.services import excel_export_service


def test_default_template_directory_is_relative_to_working_directory(monkeypatch) -> None:
    monkeypatch.delenv("APP_TEMPLATE_DIR", raising=False)

    configured = Settings(_env_file=None)  # type: ignore[call-arg]

    assert configured.template_dir == Path.cwd() / "data" / "template"


def test_load_spec_reads_configured_runtime_template(monkeypatch) -> None:
    source_template_dir = Path(__file__).parents[2] / "example" / "template"
    monkeypatch.setattr(settings, "template_dir", source_template_dir)

    spec = excel_export_service._load_spec("purchase-application.json")

    assert spec["template_name"] == "采购申请模板"


def test_missing_template_raises_readable_service_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "template_dir", tmp_path)

    with pytest.raises(AppError) as raised:
        excel_export_service._load_spec("purchase-application.json")

    assert raised.value.status_code == 400
    assert raised.value.code == "EXPORT_TEMPLATE_MISSING"
    assert "purchase-application.json" in raised.value.message


def test_invalid_template_raises_readable_business_error(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "purchase-application.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings, "template_dir", tmp_path)

    with pytest.raises(AppError) as raised:
        excel_export_service.render_excel("purchase-application.json", [])

    assert raised.value.status_code == 400
    assert raised.value.code == "EXPORT_TEMPLATE_INVALID"
