from typing import Any


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
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
