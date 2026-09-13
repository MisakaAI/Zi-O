"""管理员认证 API:登录,退出和当前会话查询."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ..errors import AppError
from ..schemas import LoginRequest
from ..security import same_origin
from ..services import auth as auth_service
from .deps import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db=Depends(get_db)):
    """校验管理员凭据并通过 HttpOnly Cookie 建立服务端会话."""
    if not same_origin(request, request.app.state.settings):
        raise AppError("origin_check_failed", "request origin is not allowed", 403)
    token, user = auth_service.login(db, payload.username, payload.password, request.app.state.settings.session_ttl_seconds)
    response.set_cookie(
        auth_service.COOKIE_NAME,
        token,
        max_age=request.app.state.settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.cookie_secure,
        path="/",
    )
    return {"user": user}


@router.post("/logout")
def logout(request: Request, response: Response, db=Depends(get_db)):
    """使当前数据库会话失效,并清除浏览器中的认证 Cookie."""
    if not same_origin(request, request.app.state.settings):
        raise AppError("origin_check_failed", "request origin is not allowed", 403)
    auth_service.logout(db, request.cookies.get(auth_service.COOKIE_NAME))
    response.delete_cookie(auth_service.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request, db=Depends(get_db)):
    """返回当前登录管理员的最小公开身份;未登录时返回 null."""
    user = auth_service.current_user(db, request.cookies.get(auth_service.COOKIE_NAME))
    return {"user": auth_service.public_user(user) if user else None}
