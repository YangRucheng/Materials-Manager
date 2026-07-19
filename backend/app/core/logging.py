from __future__ import annotations

import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


class MonthlyTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Archive each rotated daily log inside a YYYY-MM directory."""

    def rotation_filename(self, default_name: str) -> str:
        rotated_at = time.localtime(self.rolloverAt - self.interval)
        archive_dir = Path(self.baseFilename).parent / time.strftime("%Y-%m", rotated_at)
        archive_dir.mkdir(parents=True, exist_ok=True)
        base = Path(self.baseFilename)
        archive_name = f"{base.stem}.{time.strftime(self.suffix, rotated_at)}{base.suffix}"
        return str(archive_dir / archive_name)

    def getFilesToDelete(self) -> list[str]:
        if self.backupCount <= 0:
            return []

        base = Path(self.baseFilename)
        candidates: list[tuple[str, Path]] = []
        archive_dirs = [
            path
            for path in base.parent.iterdir()
            if path.is_dir() and len(path.name) == 7 and path.name[4] == "-"
        ]
        for archive_dir in archive_dirs:
            for path in archive_dir.glob(f"{base.stem}.*{base.suffix}"):
                date_text = path.name[len(base.stem) + 1 : -len(base.suffix)]
                try:
                    time.strptime(date_text, self.suffix)
                except ValueError:
                    continue
                candidates.append((date_text, path))

        candidates.sort(key=lambda item: item[0])
        excess = len(candidates) - self.backupCount
        return [str(path) for _, path in candidates[: max(excess, 0)]]


class IgnoreHealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()


def console_formatter() -> logging.Formatter:
    if os.getenv("NO_COLOR") is None:
        log_format = (
            "\033[32m%(asctime)s\033[0m | "
            "\033[33m%(levelname)-8s\033[0m | "
            "\033[36m%(name)s\033[0m | %(message)s"
        )
    else:
        log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    return logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")


def configure_logging(log_dir: Path, backup_count: int = 90) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    plain_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    plain_formatter = logging.Formatter(plain_format, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter())
    console_handler.addFilter(IgnoreHealthCheckFilter())

    file_handler = MonthlyTimedRotatingFileHandler(
        filename=log_dir / "spare-parts-api.log",
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
        utc=False,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(plain_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    for logger_name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.captureWarnings(True)
