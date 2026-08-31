import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

password_hasher = PasswordHasher()


def fernet() -> Fernet:
    """用于加密敏感凭证 / 配置的 Fernet 实例。

    优先使用独立的 APP_FERNET_KEY；未配置时回退到由 jwt_secret 派生的密钥
    （两者都经 SHA-256 固定为 32 字节），保证既有已加密数据可继续解密。
    """
    if settings.fernet_key:
        digest = hashlib.sha256(settings.fernet_key.encode("utf-8")).digest()
    else:
        digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    """加密敏感凭证（接口令牌 / API Key 等）用于落库。"""
    return fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    """解密敏感凭证；空值或解密失败（如密钥轮换）时返回 None，供读取路径优雅降级。"""
    if not value:
        return None
    try:
        return fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _create_access_token(
    subject: int | str,
    token_type: str,
    expires_minutes: int,
    **claims: str,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "token_type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        **claims,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return _create_access_token(
        user_id, "management_access", settings.access_token_minutes, jti=str(uuid4())
    )


def create_refresh_token(user_id: int, user_version: int) -> str:
    return _create_access_token(
        user_id,
        "management_refresh",
        settings.refresh_token_days * 24 * 60,
        version=str(user_version),
        jti=str(uuid4()),
    )


def create_mini_program_access_token(user_id: int) -> str:
    return _create_access_token(user_id, "mini_program", settings.access_token_minutes)


def create_mini_program_registration_token(app_id: str, openid: str) -> str:
    return _create_access_token(openid, "mini_program_registration", 10, app_id=app_id)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
