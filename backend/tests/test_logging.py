import logging
from pathlib import Path

from app.core.logging import IgnoreHealthCheckFilter, MonthlyTimedRotatingFileHandler


def test_daily_log_rotation_uses_month_directory(tmp_path: Path) -> None:
    handler = MonthlyTimedRotatingFileHandler(tmp_path / "api.log", when="midnight")
    handler.suffix = "%Y-%m-%d"
    try:
        rotated = Path(handler.rotation_filename("unused"))
    finally:
        handler.close()

    assert rotated.parent.parent == tmp_path
    assert rotated.parent.name.count("-") == 1
    assert rotated.name.startswith("api.")
    assert rotated.suffix == ".log"


def test_monthly_archives_honor_backup_count(tmp_path: Path) -> None:
    handler = MonthlyTimedRotatingFileHandler(
        tmp_path / "api.log", when="midnight", backupCount=2
    )
    handler.suffix = "%Y-%m-%d"
    archive_names = (
        "2026-04/api.2026-04-30.log",
        "2026-05/api.2026-05-01.log",
        "2026-05/api.2026-05-02.log",
    )
    try:
        for name in archive_names:
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

        files_to_delete = handler.getFilesToDelete()
    finally:
        handler.close()

    assert files_to_delete == [str(tmp_path / archive_names[0])]


def test_health_check_filter_only_suppresses_health_requests() -> None:
    health = logging.LogRecord("api", logging.INFO, "", 0, "HTTP GET /health", (), None)
    normal = logging.LogRecord("api", logging.INFO, "", 0, "HTTP GET /api/v1/users", (), None)

    log_filter = IgnoreHealthCheckFilter()

    assert not log_filter.filter(health)
    assert log_filter.filter(normal)
