from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, version_conflict
from app.models import BusinessEventLog
from app.schemas import AiSearchSettingsRead, AiSearchSettingsUpdate
from app.services.common import log_event, split_or_search_terms

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30 * 60
_MAX_EXPANSIONS_PER_TERM = 6
_SETTING_BUSINESS_TYPE = "SYSTEM_SETTING"
_SETTING_BUSINESS_ID = 1
_SETTING_ACTION = "AI_SEARCH_CONFIG_UPDATED"
_cache: dict[tuple[int, tuple[str, ...]], tuple[float, tuple[str, ...]]] = {}
_client = httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=2.0))


@dataclass(frozen=True)
class AiSearchConfig:
    endpoint: str
    api_key_encrypted: str
    model: str
    enabled: bool
    updated_at: datetime | None
    version: int


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_api_key(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode("utf-8")).decode("ascii")


def _decrypt_api_key(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError(
            "AI_API_KEY_DECRYPT_FAILED",
            "AI API Key 无法解密，请由超级管理员重新保存配置",
            status_code=503,
        ) from exc


def _completion_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return f"{endpoint}/chat/completions"


def _payload(config: AiSearchConfig) -> dict[str, object]:
    return {
        "endpoint": config.endpoint,
        "api_key_encrypted": config.api_key_encrypted,
        "model": config.model,
        "enabled": config.enabled,
    }


async def close_client() -> None:
    await _client.aclose()


async def get_setting(session: AsyncSession) -> AiSearchConfig | None:
    event = await session.scalar(
        select(BusinessEventLog)
        .where(
            BusinessEventLog.business_type == _SETTING_BUSINESS_TYPE,
            BusinessEventLog.business_id == _SETTING_BUSINESS_ID,
            BusinessEventLog.action == _SETTING_ACTION,
        )
        .order_by(BusinessEventLog.id.desc())
        .limit(1)
    )
    if event is None:
        return None
    data = event.after_data if isinstance(event.after_data, dict) else {}
    endpoint = data.get("endpoint")
    api_key_encrypted = data.get("api_key_encrypted")
    model = data.get("model")
    enabled = data.get("enabled")
    return AiSearchConfig(
        endpoint=endpoint if isinstance(endpoint, str) else "",
        api_key_encrypted=api_key_encrypted if isinstance(api_key_encrypted, str) else "",
        model=model if isinstance(model, str) else "",
        enabled=enabled if isinstance(enabled, bool) else False,
        updated_at=event.occurred_at,
        version=event.id,
    )


def setting_read(setting: AiSearchConfig | None) -> AiSearchSettingsRead:
    if setting is None:
        return AiSearchSettingsRead(
            endpoint="",
            model="",
            enabled=False,
            api_key_configured=False,
            updated_at=None,
            version=0,
        )
    return AiSearchSettingsRead(
        endpoint=setting.endpoint,
        model=setting.model,
        enabled=setting.enabled,
        api_key_configured=bool(setting.api_key_encrypted),
        updated_at=setting.updated_at,
        version=setting.version,
    )


async def update_setting(
    session: AsyncSession, data: AiSearchSettingsUpdate
) -> AiSearchConfig:
    current = await get_setting(session)
    actual_version = current.version if current else 0
    if data.version != actual_version:
        raise version_conflict(data.version, actual_version)
    if not (current and current.api_key_encrypted) and not data.api_key:
        raise AppError("AI_API_KEY_REQUIRED", "尚未配置 API Key，请先填写")

    api_key_encrypted = current.api_key_encrypted if current else ""
    if data.clear_api_key:
        api_key_encrypted = ""
    elif data.api_key:
        api_key_encrypted = _encrypt_api_key(data.api_key)

    event = await log_event(
        session,
        business_type=_SETTING_BUSINESS_TYPE,
        business_id=_SETTING_BUSINESS_ID,
        action=_SETTING_ACTION,
        old_status="启用" if current and current.enabled else "停用",
        new_status="启用" if data.enabled else "停用",
        remark="超级管理员更新 AI 搜索配置",
        before_data=_payload(current) if current else None,
        after_data={
            "endpoint": data.endpoint.rstrip("/"),
            "api_key_encrypted": api_key_encrypted,
            "model": data.model,
            "enabled": data.enabled,
        },
    )
    _cache.clear()
    return AiSearchConfig(
        endpoint=data.endpoint.rstrip("/"),
        api_key_encrypted=api_key_encrypted,
        model=data.model,
        enabled=data.enabled,
        updated_at=event.occurred_at,
        version=event.id,
    )


async def is_available(session: AsyncSession) -> bool:
    setting = await get_setting(session)
    return bool(setting and setting.enabled and setting.api_key_encrypted)


def _search_terms(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(dict.fromkeys(split_or_search_terms(value)))


def _extract_json(content: str) -> dict[str, Any]:
    content = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.DOTALL)
    if fenced:
        content = fenced.group(1)
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AppError("AI_INVALID_RESPONSE", "AI 返回内容不是有效 JSON", status_code=502) from exc
    if not isinstance(payload, dict):
        raise AppError("AI_INVALID_RESPONSE", "AI 返回结构无效", status_code=502)
    return payload


async def _request_expansions(setting: AiSearchConfig, terms: tuple[str, ...]) -> tuple[str, ...]:
    cache_key = (setting.version, terms)
    cached = _cache.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    api_key = _decrypt_api_key(setting.api_key_encrypted)
    prompt = (
        "你是工业备件搜索词扩展器。为每个输入词补充同义词、常用别名和规范名称，"
        "只补充含义高度一致、适合数据库模糊搜索的短词。不要补充上下位类别、品牌或型号。"
        "每个输入最多返回5个补充词，必须保留原词。只返回JSON："
        '{"expansions":[["原词","同义词"]]}。输入词：'
        + json.dumps(terms, ensure_ascii=False)
    )
    try:
        response = await _client.post(
            _completion_url(setting.endpoint),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": setting.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 180,
            },
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise AppError(
            "AI_REQUEST_FAILED",
            "AI 搜索扩展服务调用失败",
            status_code=502,
            details={"reason": str(exc)[:300]},
        ) from exc

    payload = _extract_json(content)
    groups = payload.get("expansions")
    if not isinstance(groups, list) or len(groups) != len(terms):
        raise AppError("AI_INVALID_RESPONSE", "AI 返回的扩展词数量不匹配", status_code=502)

    expanded: list[str] = []
    seen: set[str] = set()
    for original, group in zip(terms, groups, strict=True):
        candidates = [original]
        if isinstance(group, list):
            candidates.extend(str(item).strip() for item in group if isinstance(item, str))
        for candidate in candidates[:_MAX_EXPANSIONS_PER_TERM]:
            if candidate and len(candidate) <= 64 and candidate not in seen:
                expanded.append(candidate)
                seen.add(candidate)
    result = tuple(expanded)
    _cache[cache_key] = (now, result)
    return result


async def expand_search_value(
    session: AsyncSession, value: str | None, *, strict: bool = False
) -> str | None:
    terms = _search_terms(value)
    if not terms:
        return value
    setting = await get_setting(session)
    if not setting or not setting.enabled or not setting.api_key_encrypted:
        if strict:
            raise AppError("AI_NOT_CONFIGURED", "AI 搜索服务未启用或配置不完整", status_code=503)
        return value
    try:
        expanded = await _request_expansions(setting, terms)
    except AppError:
        if strict:
            raise
        logger.warning("AI search expansion failed; using original terms", exc_info=True)
        return value
    return "|".join(expanded)
