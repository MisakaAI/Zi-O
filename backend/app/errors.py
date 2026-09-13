"""应用层稳定错误类型,供 API 统一转换为错误响应."""

from __future__ import annotations


class AppError(Exception):
    """携带错误码,用户消息,HTTP 状态和可选详情的业务异常."""

    def __init__(self, code: str, message: str, status_code: int = 400, details: object | None = None):
        """保存 API 所需的结构化错误信息,同时保留异常语义."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
