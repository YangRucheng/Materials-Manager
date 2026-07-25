from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    ("raw_origins", "expected"),
    [
        (
            '["https://web.example.com","https://admin.example.com/"]',
            ["https://web.example.com", "https://admin.example.com"],
        ),
        (
            "https://web.example.com, https://admin.example.com/",
            ["https://web.example.com", "https://admin.example.com"],
        ),
    ],
)
def test_cors_origins_support_json_and_comma_separated_values(
    monkeypatch: pytest.MonkeyPatch,
    raw_origins: str,
    expected: list[str],
) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", raw_origins)

    configured = Settings(_env_file=None)  # type: ignore[call-arg]

    assert configured.cors_origins == expected


def test_cors_origin_regex_accepts_empty_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGIN_REGEX", "  ")

    configured = Settings(_env_file=None)  # type: ignore[call-arg]

    assert configured.cors_origin_regex is None


def test_default_cors_reflects_any_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("APP_CORS_ORIGIN_REGEX", raising=False)
    monkeypatch.delenv("APP_CORS_ALLOW_CREDENTIALS", raising=False)

    configured = Settings(_env_file=None)  # type: ignore[call-arg]

    assert configured.cors_origins == []
    assert configured.cors_origin_regex == ".*"
    assert configured.cors_allow_credentials is True


def test_cors_origin_rejects_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", "https://web.example.com/app")

    with pytest.raises(ValidationError, match="invalid CORS origin"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_wildcard_cors_requires_credentials_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", "*")
    monkeypatch.setenv("APP_CORS_ALLOW_CREDENTIALS", "true")

    with pytest.raises(ValidationError, match="APP_CORS_ALLOW_CREDENTIALS"):
        Settings(_env_file=None)  # type: ignore[call-arg]

    monkeypatch.setenv("APP_CORS_ALLOW_CREDENTIALS", "false")
    configured = Settings(_env_file=None)  # type: ignore[call-arg]

    assert configured.cors_origins == ["*"]
    assert configured.cors_allow_credentials is False
