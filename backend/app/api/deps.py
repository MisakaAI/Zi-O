from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Request

from ..db.connection import connect
from ..errors import AppError
from ..security import same_origin
from ..services.auth import COOKIE_NAME, current_user


def get_db(request: Request) -> Generator:
    db = connect(request.app.state.settings.database_path)
    try:
        yield db
    finally:
        db.close()


def require_user(request: Request, db=Depends(get_db)):
    user = current_user(db, request.cookies.get(COOKIE_NAME))
    if user is None:
        raise AppError("authentication_required", "administrator authentication is required", 401)
    request.state.user = user
    return user


def require_write_origin(request: Request) -> None:
    if request.app.state.settings.environment != "test" and not same_origin(request, request.app.state.settings):
        raise AppError("origin_check_failed", "request origin is not allowed", 403)
