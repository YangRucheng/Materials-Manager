from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
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
    access_token_minutes: int = Field(default=30, ge=1)
    refresh_token_days: int = Field(default=7, ge=1)
    # 加密 API Key / Webhook 密钥等敏感配置的 Fernet 密钥（可选的独立密钥）。
    # 留空时回退到由 jwt_secret 派生的密钥，保证既有已加密数据可继续解密；
    # 设置后优先使用独立密钥（新部署建议固定配置，避免轮换 jwt_secret 连带失效）。
    fernet_key: str = ""
    wechat_mini_program_app_id: str = ""
    wechat_mini_program_app_secret: str = ""
    upload_dir: Path = BACKEND_DIR / "data" / "uploads"
    template_dir: Path = BACKEND_DIR / "app" / "templates"
    log_dir: Path = BACKEND_DIR / "data" / "logs"
    log_backup_count: int = Field(default=90, ge=1)
    max_image_bytes: int = 10 * 1024 * 1024
    # 允许跨域来源白名单（逗号分隔的 origin，如 "https://app.example.com,.example.com"）。
    # 空列表表示不限制（开发环境默认）。生产环境务必配置为前端实际访问域名。
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    cors_allow_credentials: bool = True
    cors_max_age: int = Field(default=86400, ge=0)
    # 每日凌晨2点定时清理已转入申购记录的计划（记录自包含快照后删除计划是安全的）
    purchase_plan_cleanup_enabled: bool = True
    # 构建期注入的版本信息（Docker ARG/ENV，见 backend/Dockerfile 与 CI build-images.yml）
    build_time: str | None = None
    git_sha: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
