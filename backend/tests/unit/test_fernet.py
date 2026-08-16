from __future__ import annotations

import pytest

from app.services.common import fernet


def test_fernet_roundtrip_within_session() -> None:
    value = "super-secret-api-key"
    encrypted = fernet().encrypt(value.encode("utf-8")).decode("ascii")
    assert encrypted != value
    assert fernet().decrypt(encrypted.encode("ascii")).decode("utf-8") == value


def test_fernet_falls_back_to_jwt_derived_key() -> None:
    """未配置 APP_FERNET_KEY 时应回退到 jwt_secret 派生密钥（向后兼容）。"""
    from app.core.config import settings

    assert not settings.fernet_key  # 测试环境未设置独立密钥
    import base64
    import hashlib

    from cryptography.fernet import Fernet as CryptographyFernet

    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    expected = CryptographyFernet(base64.urlsafe_b64encode(digest))
    value = "legacy-encrypted-value"
    encrypted = expected.encrypt(value.encode("utf-8")).decode("ascii")
    # 既有用 jwt 派生密钥加密的数据必须能被共享 fernet() 解密
    assert fernet().decrypt(encrypted.encode("ascii")).decode("utf-8") == value