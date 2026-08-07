# API 错误与状态码约定

## 核心约定：禁止 HTTP 404

**本项目对外 API 不使用 HTTP 404 状态码。**

`404 Not Found` 语义模糊：它既能表示「这个 URL 不存在」，也能表示「这个资源不存在」，
而这两种含义在本系统中必须区分处理。前者是路径错误，后者是正常业务分支。

### 资源不存在 → HTTP 400 + `code=NOT_FOUND`

按 ID / UUID 查询不存在的资源（物资、用户、流水、图片等），统一返回：

```json
{
  "code": "NOT_FOUND",
  "message": "二级库物资不存在",
  "details": {},
  "request_id": "…"
}
```

- HTTP 状态码：**400**（通过 `app.core.errors.not_found()` / `AppError("NOT_FOUND", …)` 生成）。
- 客户端按响应体 `code == "NOT_FOUND"` 区分，不依赖 HTTP 状态码。
- 原因：资源不存在是本系统的正常业务分支（删除后查详情、跨库校验、隐藏计划等），
  用 400 表达「该请求无法满足」，避免与路径错误混淆。

### 未匹配路径 → HTTP 400 + `code=ROUTE_NOT_FOUND`

请求打到不存在的 API 路径时，框架默认会返回 404。本项目在 `app/main.py` 通过
`StarletteHTTPException` 全局处理，将 404 重映射为：

```json
{
  "code": "ROUTE_NOT_FOUND",
  "message": "接口路径不存在",
  "details": {},
  "request_id": "…"
}
```

- HTTP 状态码：**400**。
- 确保系统对外任何情况下都不产生 404 状态码，返回体保持统一结构（含 `request_id`）。
- 其余 Starlette HTTP 异常（如 405 Method Not Allowed、422）保持原状态码透传，不做重映射。

### 不在约定范围内

- **前端路由级「页面不存在」**（`frontend/src/views/NotFoundView.vue`）：属于浏览器端 UI
  展示，不涉及 HTTP 状态码。
- **对上游服务的 404 适配**（`ai_search_service` 判断上游 AI 接口 404 并转换为
  `AI_ENDPOINT_NOT_FOUND`）：这是消费外部服务的逻辑，不属于本 API 契约，可自由使用 404 判断。

## 错误响应体结构

所有业务错误（含上述两类）统一返回结构化 JSON：

```json
{
  "code": "VERSION_CONFLICT",
  "message": "数据已被其他用户修改，请刷新后重试",
  "details": {"expected": 3, "actual": 5},
  "request_id": "…"
}
```

| 字段 | 说明 |
| --- | --- |
| `code` | 业务错误码，全局唯一（如 `NOT_FOUND`、`VERSION_CONFLICT`、`VALIDATION_ERROR`） |
| `message` | 人类可读的中文提示 |
| `details` | 可选的结构化详情（校验错误、版本号等） |
| `request_id` | 请求追踪 ID，与应用日志关联 |

## 状态码使用总表

| HTTP 状态码 | 用途 | 说明 |
| --- | --- | --- |
| 200 / 201 / 204 | 成功 | 创建 201、无内容 204 |
| 400 | 请求无法满足 | 业务校验失败、**资源不存在（`NOT_FOUND`）**、**路径不存在（`ROUTE_NOT_FOUND`）** |
| 401 | 未认证或凭证无效 | `INVALID_TOKEN`、`UNAUTHORIZED` |
| 403 | 权限不足 / 账号禁用 | `FORBIDDEN`、`ACCOUNT_DISABLED` |
| 409 | 版本冲突 / 数据约束冲突 | `VERSION_CONFLICT`、`DATA_CONFLICT`、`INVALID_STATUS_TRANSITION` |
| 422 | 请求参数校验失败 | 请求体字段不合法（Pydantic 校验） |
| 429 | 上游限流透传 | `AI_RATE_LIMITED` |
| 500 | 服务内部错误 | `INTERNAL_SERVER_ERROR`、`DATABASE_QUERY_ERROR` |
| 502 / 503 | 上游不可用 / 服务不可用 | `AI_UPSTREAM_FAILED`、`DATABASE_UNAVAILABLE` |

## 代码实现位置

- 后端错误码 → 默认状态码映射：`backend/app/core/errors.py`
- 业务错误全局处理：`backend/app/main.py`（`handle_app_error`）
- 框架级 404 重映射：`backend/app/main.py`（`handle_http_exception`）
- 前端 mock 与后端保持一致的映射：`frontend/src/mocks/handlers.ts`（`DEFAULT_STATUS_BY_CODE`）
