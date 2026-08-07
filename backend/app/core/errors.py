from typing import Any

# 业务错误码 → 默认 HTTP 状态码映射。
# 传了 status_code 时以显式值为准；未传时按 code 推断，避免同类错误状态码不一致。
#
# 约定：本项目禁用 HTTP 404 状态码（见 docs/api-error-conventions.md）。
# 「资源不存在」属于正常业务分支，统一用 400 + code=NOT_FOUND 表达，
# 由前端按业务码区分，避免与「路由/文件不存在」的 404 混淆。
_DEFAULT_STATUS_BY_CODE: dict[str, int] = {
    "NOT_FOUND": 400,
    "VERSION_CONFLICT": 409,
    "INVALID_STATUS_TRANSITION": 409,
    "DATA_CONFLICT": 409,
    "INVALID_TOKEN": 401,
    "UNAUTHORIZED": 401,
    "USER_DISABLED": 401,
    "ACCOUNT_DISABLED": 403,
    "FORBIDDEN": 403,
    "VALIDATION_ERROR": 422,
}


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code or _DEFAULT_STATUS_BY_CODE.get(code, 400)
        self.details = details or {}


def not_found(resource: str = "资源") -> AppError:
    return AppError("NOT_FOUND", f"{resource}不存在")


def version_conflict(expected: int, actual: int) -> AppError:
    return AppError(
        "VERSION_CONFLICT",
        "数据已被其他用户修改，请刷新后重试",
        status_code=409,
        details={"expected": expected, "actual": actual},
    )


def invalid_transition(current: str, action: str) -> AppError:
    return AppError(
        "INVALID_STATUS_TRANSITION",
        "当前状态不允许执行此操作",
        status_code=409,
        details={"current_status": current, "action": action},
    )
