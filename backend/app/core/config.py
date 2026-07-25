from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_prefix="APP_", extra="ignore"
    )

    app_name: str = "电气车间备件管理系统"
    environment: str = "development"
    database_url: str = "mysql+asyncmy://spare:spare@mysql:3306/spare_parts?charset=utf8mb4"
    jwt_secret: str = Field(default="change-me-in-production", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    wechat_mini_program_app_id: str = ""
    wechat_mini_program_app_secret: str = ""
    upload_dir: Path = BACKEND_DIR / "data" / "uploads"
    template_dir: Path = BACKEND_DIR / "app" / "templates"
    log_dir: Path = BACKEND_DIR / "data" / "logs"
    log_backup_count: int = Field(default=90, ge=1)
    max_image_bytes: int = 10 * 1024 * 1024
    cors_origins: Annotated[list[str], NoDecode] = []
    cors_origin_regex: str | None = ".*"
    cors_allow_credentials: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        raw_value = value.strip()
        if not raw_value:
            return []
        if raw_value.startswith("["):
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise ValueError("CORS origins must be valid JSON or comma-separated") from exc
            if not isinstance(parsed, list):
                raise ValueError("CORS origins JSON value must be an array")
            return parsed
        return raw_value.split(",")

    @field_validator("cors_origins")
    @classmethod
    def normalize_cors_origins(cls, origins: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw_origin in origins:
            origin = raw_origin.strip()
            if not origin:
                continue
            if origin in {"*", "null"}:
                normalized.append(origin)
                continue
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"invalid CORS origin: {origin}")
            normalized.append(f"{parsed.scheme.lower()}://{parsed.netloc.lower()}")
        return list(dict.fromkeys(normalized))

    @field_validator("cors_origin_regex", mode="before")
    @classmethod
    def normalize_cors_origin_regex(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        pattern = value.strip()
        if not pattern:
            return None
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError("invalid CORS origin regex") from exc
        return pattern

    @model_validator(mode="after")
    def validate_cors_credentials(self) -> Settings:
        if "*" in self.cors_origins and self.cors_allow_credentials:
            raise ValueError(
                "APP_CORS_ALLOW_CREDENTIALS must be false when APP_CORS_ORIGINS contains '*'"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
