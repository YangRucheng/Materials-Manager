from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    upload_dir: Path = BACKEND_DIR / "data" / "uploads"
    template_dir: Path = BACKEND_DIR / "data" / "template"
    max_image_bytes: int = 10 * 1024 * 1024
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
