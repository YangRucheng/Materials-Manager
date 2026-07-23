from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NoReturn

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
_RESPONSE_TIMEOUT_SECONDS = 10.0
_TEST_RESPONSE_TIMEOUT_SECONDS = 30.0
_CONNECT_TIMEOUT_SECONDS = 3.0
_cache: dict[tuple[int, tuple[str, ...]], tuple[float, tuple[str, ...]]] = {}
_client = httpx.AsyncClient(
    timeout=httpx.Timeout(_RESPONSE_TIMEOUT_SECONDS, connect=_CONNECT_TIMEOUT_SECONDS)
)


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
            api_key="",
            model="",
            enabled=False,
            updated_at=None,
            version=0,
        )
    return AiSearchSettingsRead(
        endpoint=setting.endpoint,
        api_key=_decrypt_api_key(setting.api_key_encrypted) if setting.api_key_encrypted else "",
        model=setting.model,
        enabled=setting.enabled,
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
    api_key_encrypted = _encrypt_api_key(data.api_key)

    event = await log_event(
        session,
        business_type=_SETTING_BUSINESS_TYPE,
        business_id=_SETTING_BUSINESS_ID,
        action=_SETTING_ACTION,
        old_status="启用" if current and current.enabled else "停用",
        new_status="启用" if data.enabled else "停用",
        remark="超级管理员更新大模型配置",
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
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, character in enumerate(content):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(content[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise AppError(
            "AI_INVALID_RESPONSE",
            "AI 返回内容不是有效 JSON，请检查模型是否支持 JSON 输出模式",
            status_code=502,
            details={"content_preview": content[:300]},
        ) from None
    if isinstance(payload, dict):
        return payload
    raise AppError(
        "AI_INVALID_RESPONSE",
        "AI 返回的 JSON 顶层结构不是对象",
        status_code=502,
        details={"content_preview": content[:300]},
    )


def _completion_payload(setting: AiSearchConfig, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": setting.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 180,
        "stream": False,
    }
    if setting.model.strip().lower().startswith("glm-"):
        payload["thinking"] = {"type": "disabled"}
        payload["response_format"] = {"type": "json_object"}
    return payload


def _upstream_error_reason(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"][:300]
    if isinstance(error, str):
        return error[:300]
    for key in ("message", "detail"):
        value = payload.get(key)
        if isinstance(value, str):
            return value[:300]
    return None


def _raise_upstream_status_error(exc: httpx.HTTPStatusError) -> NoReturn:
    status = exc.response.status_code
    reason = _upstream_error_reason(exc.response)
    details: dict[str, object] = {"upstream_status": status}
    if reason:
        details["reason"] = reason

    if status in {401, 403}:
        code = "AI_AUTH_FAILED"
        message = "AI 服务鉴权失败，请检查 API Key 是否正确且具有模型访问权限"
        response_status = 400
    elif status == 404:
        code = "AI_ENDPOINT_NOT_FOUND"
        message = "AI 接口或模型不存在，请检查端点路径和模型名称"
        response_status = 400
    elif status == 429:
        code = "AI_RATE_LIMITED"
        message = "AI 服务请求过于频繁或额度不足，请检查账户额度后重试"
        response_status = 429
    elif 400 <= status < 500:
        code = "AI_REQUEST_REJECTED"
        message = "AI 服务拒绝了请求，请检查端点格式、模型名称和接口兼容性"
        response_status = 400
    else:
        code = "AI_UPSTREAM_FAILED"
        message = f"AI 上游服务返回 HTTP {status}，请检查服务状态或稍后重试"
        response_status = 502

    if reason:
        message = f"{message}：{reason}"
    raise AppError(code, message, status_code=response_status, details=details) from exc


async def _request_expansions(
    setting: AiSearchConfig,
    terms: tuple[str, ...],
    *,
    response_timeout_seconds: float,
) -> tuple[str, ...]:
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
    completion_url = _completion_url(setting.endpoint)
    try:
        response = await _client.post(
            completion_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=_completion_payload(setting, prompt),
            timeout=httpx.Timeout(response_timeout_seconds, connect=_CONNECT_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
    except httpx.ConnectTimeout as exc:
        raise AppError(
            "AI_CONNECT_TIMEOUT",
            f"连接 AI 服务超时（{_CONNECT_TIMEOUT_SECONDS:g} 秒），"
            "请检查端点地址、服务器网络或代理设置",
            status_code=400,
            details={"timeout_seconds": _CONNECT_TIMEOUT_SECONDS, "endpoint": completion_url},
        ) from exc
    except httpx.ReadTimeout as exc:
        logger.warning(
            "AI response timeout phase=response_wait endpoint=%s model=%s timeout_seconds=%s",
            completion_url,
            setting.model,
            response_timeout_seconds,
        )
        raise AppError(
            "AI_RESPONSE_TIMEOUT",
            "已连接 AI 服务并发送请求，但在等待上游响应数据阶段，"
            f"模型「{setting.model}」于 {response_timeout_seconds:g} 秒内未返回完整响应。"
            f"端点：{completion_url}。"
            "这通常表示模型冷启动、推理阻塞或上游代理读取超时，请检查上游请求日志",
            status_code=400,
            details={
                "phase": "response_wait",
                "timeout_seconds": response_timeout_seconds,
                "endpoint": completion_url,
                "model": setting.model,
                "suggestion": "检查上游模型运行日志、冷启动状态和反向代理读取超时",
            },
        ) from exc
    except httpx.TimeoutException as exc:
        raise AppError(
            "AI_REQUEST_TIMEOUT",
            f"AI 服务请求超时（{response_timeout_seconds:g} 秒），请稍后重试",
            status_code=400,
            details={"timeout_seconds": response_timeout_seconds, "endpoint": completion_url},
        ) from exc
    except httpx.ConnectError as exc:
        raise AppError(
            "AI_CONNECTION_FAILED",
            "无法连接 AI 服务，请检查端点地址、DNS、TLS 证书或服务器出网配置",
            status_code=400,
            details={"reason": str(exc)[:300], "endpoint": completion_url},
        ) from exc
    except httpx.HTTPStatusError as exc:
        _raise_upstream_status_error(exc)
    except httpx.RequestError as exc:
        raise AppError(
            "AI_REQUEST_FAILED",
            "请求 AI 服务失败，请检查端点和服务器网络配置",
            status_code=400,
            details={"reason": str(exc)[:300], "endpoint": completion_url},
        ) from exc

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except ValueError as exc:
        raise AppError(
            "AI_INVALID_RESPONSE",
            "AI 服务返回了无法解析的 JSON 响应",
            status_code=502,
        ) from exc
    except (KeyError, IndexError, TypeError) as exc:
        raise AppError(
            "AI_INVALID_RESPONSE",
            "AI 服务返回结构缺少 choices[0].message.content，请检查接口兼容性",
            status_code=502,
        ) from exc
    if not isinstance(content, str):
        raise AppError(
            "AI_INVALID_RESPONSE",
            "AI 服务返回的 message.content 不是文本，请检查接口兼容性",
            status_code=502,
        )

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
    session: AsyncSession,
    value: str | None,
    *,
    strict: bool = False,
    response_timeout_seconds: float = _RESPONSE_TIMEOUT_SECONDS,
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
        expanded = await _request_expansions(
            setting,
            terms,
            response_timeout_seconds=response_timeout_seconds,
        )
    except AppError:
        if strict:
            raise
        logger.warning("AI search expansion failed; using original terms", exc_info=True)
        return value
    return "|".join(expanded)


async def test_search_value(session: AsyncSession, value: str) -> str | None:
    return await expand_search_value(
        session,
        value,
        strict=True,
        response_timeout_seconds=_TEST_RESPONSE_TIMEOUT_SECONDS,
    )
