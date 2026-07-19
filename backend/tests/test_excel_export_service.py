from pathlib import Path

from app.core.config import settings
from app.services import excel_export_service


def test_load_spec_falls_back_to_packaged_template(
    monkeypatch, tmp_path: Path
) -> None:
    source_template_dir = Path(__file__).parents[1] / "data" / "template"
    monkeypatch.setattr(settings, "template_dir", tmp_path)
    monkeypatch.setattr(excel_export_service, "PACKAGED_TEMPLATE_DIR", source_template_dir)

    spec = excel_export_service._load_spec("purchase-application.json")

    assert spec["template_name"] == "采购申请模板"
