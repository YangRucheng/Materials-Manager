from __future__ import annotations

import base64
import binascii
import re
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qs, quote

import httpx
from fastapi import FastAPI
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.database import SessionLocal
from app.core.permissions import find_user_by_api_token

MAX_BINARY_RESPONSE_BYTES = 25 * 1024 * 1024
EXCLUDED_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
}
EXCLUDED_PREFIXES = (
    "/api/v1/agent/database",
    "/api/v1/mini-program/",
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@dataclass(frozen=True)
class McpIdentity:
    id: int
    username: str
    display_name: str
    role: str


class McpFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    mime_type: str = Field(default="application/octet-stream", min_length=1, max_length=128)


_application: FastAPI | None = None
_token_context: ContextVar[str | None] = ContextVar("mcp_api_token", default=None)
_identity_context: ContextVar[McpIdentity | None] = ContextVar("mcp_identity", default=None)

mcp = MCPServer(
    "spare-parts-management",
    title="备件管理系统",
    description="通过受控业务接口操作备件、库存、申购、用户、系统配置和附件。",
    instructions=(
        "先调用 operations_list 查找操作，再调用 operation_describe 确认参数，最后使用 "
        "operation_call 执行。不得猜测 operation_id 或绕过现有业务接口。"
    ),
)


def bind_application(application: FastAPI) -> None:
    global _application
    _application = application


def _require_application() -> FastAPI:
    if _application is None:
        raise RuntimeError("MCP 服务尚未绑定应用")
    return _application


def _require_token() -> str:
    token = _token_context.get()
    if token is None:
        raise RuntimeError("MCP 请求未通过接口令牌认证")
    return token


def _operation_catalog() -> dict[str, dict[str, Any]]:
    schema = _require_application().openapi()
    schemas = schema.get("components", {}).get("schemas", {})
    catalog: dict[str, dict[str, Any]] = {}
    for path, path_item in schema.get("paths", {}).items():
        if path in EXCLUDED_PATHS or path.startswith(EXCLUDED_PREFIXES):
            continue
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                continue
            details = {
                "operation_id": operation_id,
                "method": method.upper(),
                "path": path,
                "summary": operation.get("summary", ""),
                "description": operation.get("description", ""),
                "tags": operation.get("tags", []),
                "parameters": operation.get("parameters", []),
                "request_body": operation.get("requestBody"),
                "responses": operation.get("responses", {}),
            }
            details["schemas"] = _referenced_schemas(details, schemas)
            catalog[operation_id] = details
    return catalog


def _referenced_schemas(value: Any, schemas: dict[str, Any]) -> dict[str, Any]:
    names: set[str] = set()

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            reference = node.get("$ref")
            prefix = "#/components/schemas/"
            if isinstance(reference, str) and reference.startswith(prefix):
                name = reference.removeprefix(prefix)
                if name not in names and name in schemas:
                    names.add(name)
                    collect(schemas[name])
            for child in node.values():
                collect(child)
        elif isinstance(node, list):
            for child in node:
                collect(child)

    collect(value)
    return {name: schemas[name] for name in sorted(names)}


@mcp.tool(
    title="查看当前身份",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def system_whoami() -> dict[str, Any]:
    """返回当前 MCP 令牌对应的管理端用户及角色。"""
    identity = _identity_context.get()
    if identity is None:
        raise RuntimeError("MCP 请求未通过接口令牌认证")
    return asdict(identity)


@mcp.tool(
    title="查询可用操作",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def operations_list(
    category: str | None = None, keyword: str | None = None
) -> dict[str, Any]:
    """列出可调用的业务操作。category 按接口标签筛选，keyword 按名称和说明搜索。"""
    operations = list(_operation_catalog().values())
    if category:
        normalized_category = category.casefold()
        operations = [
            item
            for item in operations
            if any(normalized_category in str(tag).casefold() for tag in item["tags"])
        ]
    if keyword:
        normalized_keyword = keyword.casefold()
        operations = [
            item
            for item in operations
            if normalized_keyword
            in " ".join(
                [item["operation_id"], item["summary"], item["description"], *item["tags"]]
            ).casefold()
        ]
    concise = [
        {
            "operation_id": item["operation_id"],
            "method": item["method"],
            "path": item["path"],
            "summary": item["summary"],
            "tags": item["tags"],
        }
        for item in operations
    ]
    return {"count": len(concise), "operations": concise}


@mcp.tool(
    title="查看操作参数",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def operation_describe(operation_id: str) -> dict[str, Any]:
    """返回指定业务操作的路径参数、查询参数、请求体和响应契约。"""
    operation = _operation_catalog().get(operation_id)
    if operation is None:
        raise ValueError(f"未知或不允许的 operation_id: {operation_id}")
    return operation


def _build_path(path_template: str, path_params: dict[str, Any]) -> str:
    required = set(re.findall(r"{([^{}]+)}", path_template))
    missing = required - path_params.keys()
    extra = path_params.keys() - required
    if missing:
        raise ValueError(f"缺少路径参数: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"存在未定义的路径参数: {', '.join(sorted(extra))}")
    path = path_template
    for name in required:
        path = path.replace(f"{{{name}}}", quote(str(path_params[name]), safe=""))
    return path


def _binary_result(response: httpx.Response) -> dict[str, Any]:
    if len(response.content) > MAX_BINARY_RESPONSE_BYTES:
        raise ValueError("接口返回文件超过 25 MB，无法通过 MCP 返回")
    disposition = response.headers.get("content-disposition", "")
    filename_match = re.search(r'filename="?([^";]+)', disposition, flags=re.IGNORECASE)
    return {
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", "application/octet-stream"),
        "filename": filename_match.group(1) if filename_match else None,
        "content_base64": base64.b64encode(response.content).decode("ascii"),
    }


@mcp.tool(
    title="执行业务操作",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
async def operation_call(
    operation_id: str,
    path_params: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | list[Any] | None = None,
    file: McpFileInput | None = None,
) -> dict[str, Any]:
    """调用一个已登记的业务操作；附件使用 file.content_base64 传入。"""
    operation = _operation_catalog().get(operation_id)
    if operation is None:
        raise ValueError(f"未知或不允许的 operation_id: {operation_id}")
    path = _build_path(operation["path"], path_params or {})
    request_kwargs: dict[str, Any] = {
        "method": operation["method"],
        "url": path,
        "params": query or {},
        "headers": {"X-API-Token": _require_token()},
    }
    if file is not None:
        if body is not None:
            raise ValueError("文件上传操作不能同时传 body")
        try:
            content = base64.b64decode(file.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("file.content_base64 不是有效的 Base64") from exc
        request_kwargs["files"] = {
            "file": (file.filename, content, file.mime_type),
        }
    elif body is not None:
        request_kwargs["json"] = body

    transport = httpx.ASGITransport(app=_require_application())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://mcp.internal",
        follow_redirects=True,
        timeout=60,
    ) as client:
        response = await client.request(**request_kwargs)

    content_type = response.headers.get("content-type", "").lower()
    if response.status_code == 204 or not response.content:
        return {"status_code": response.status_code, "data": None}
    if "application/json" in content_type:
        return {"status_code": response.status_code, "data": response.json()}
    return _binary_result(response)


async def _send_auth_error(send: Send, message: str) -> None:
    body = (f'{{"code":"INVALID_TOKEN","message":"{message}"}}').encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class McpTokenAuthMiddleware:
    def __init__(self, application: ASGIApp):
        self.application = application

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return
        query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
        token = query.get("token", [None])[0]
        if not token:
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            token = headers.get(b"x-api-token", b"").decode("latin-1") or None
            authorization = headers.get(b"authorization", b"").decode("latin-1")
            scheme, _, credential = authorization.partition(" ")
            if not token and scheme.casefold() == "bearer" and credential:
                token = credential
        if not token:
            await _send_auth_error(send, "缺少 MCP 接口令牌")
            return

        async with SessionLocal() as session:
            user = await find_user_by_api_token(session, token)
        if user is None or not user.enabled:
            await _send_auth_error(send, "MCP 接口令牌无效或用户已停用")
            return

        identity = McpIdentity(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role.value,
        )
        token_marker = _token_context.set(token)
        identity_marker = _identity_context.set(identity)
        try:
            await self.application(scope, receive, send)
        finally:
            _identity_context.reset(identity_marker)
            _token_context.reset(token_marker)


# The endpoint is deployed behind a reverse proxy (1panel/nginx) and
# authenticated by McpTokenAuthMiddleware (X-API-Token header or ?token query),
# not by ambient browser cookies, so the SDK's default localhost-only DNS
# rebinding allowlist would reject the real public Host header with 421. Keep
# the transport-level host check disabled.
mcp_http_app = McpTokenAuthMiddleware(
    mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        max_request_body_size=16 * 1024 * 1024,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )
)
