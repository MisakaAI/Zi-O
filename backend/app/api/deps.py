"""FastAPI 依赖:按请求管理数据库连接,管理员鉴权和写来源校验."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Request

from ..db.connection import connect
from ..errors import AppError
from ..security import same_origin
from ..services.auth import COOKIE_NAME, current_user


def get_db(request: Request) -> Generator:
    """为单个请求打开数据库连接,并在请求结束后关闭它."""
    db = connect(request.app.state.settings.database_path)
    try:
        yield db
    finally:
        db.close()


def require_user(request: Request, db=Depends(get_db)):
    """要求请求携带有效管理员会话,并把身份放入请求状态."""
    user = current_user(db, request.cookies.get(COOKIE_NAME))
    if user is None:
        raise AppError("authentication_required", "administrator authentication is required", 401)
    request.state.user = user
    return user


def require_write_origin(request: Request) -> None:
    """阻止非测试环境中的跨来源写请求,降低 CSRF 风险."""
    if request.app.state.settings.environment != "test" and not same_origin(request, request.app.state.settings):
        raise AppError("origin_check_failed", "request origin is not allowed", 403)
