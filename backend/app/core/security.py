from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

password_hasher = PasswordHasher()


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
