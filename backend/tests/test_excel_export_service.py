from pathlib import Path

from app.core.config import Settings, settings
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
