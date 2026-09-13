"""组装 FastAPI 应用,挂载路由,并保护静态页和正文图片入口."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.auth import router as auth_router
from .api.deps import get_db
from .api.manage import router as manage_router
from .api.public import router as public_router
from .config import Settings
from .db.connection import connect
from .db.migrations import migrate
from .errors import AppError
from .files import resolve_static, resolve_upload
from .repositories import content as repo


def create_app(settings: Settings | None = None) -> FastAPI:
    """初始化目录和数据库迁移,注册 API,静态资源,异常处理及 SPA 回退."""
    settings = settings or Settings.from_env()
    settings.ensure_directories()
    migrate(settings.database_path, Path(__file__).parents[1] / "migrations")
    # 环境时区只用于填充刚创建的设置行;之后以管理员在数据库中的设置为准.
    with connect(settings.database_path) as db:
        row = db.execute("SELECT timezone, updated_at FROM settings WHERE id=1").fetchone()
        if row and row["updated_at"] == 0 and row["timezone"] != settings.timezone:
            db.execute("UPDATE settings SET timezone=? WHERE id=1", (settings.timezone,))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """提供 FastAPI 生命周期钩子;当前启动工作已在 create_app 中完成."""
        yield

    app = FastAPI(title="ZI/O", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(auth_router)
    app.include_router(public_router)
    app.include_router(manage_router)

    if (settings.frontend_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=settings.frontend_dist / "assets"), name="assets")

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        """把业务异常转换为不泄露内部细节的统一错误 JSON."""
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message, **({"details": exc.details} if exc.details is not None else {})}})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """把 FastAPI/Pydantic 输入校验错误转换为统一 422 响应."""
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "request validation failed", "details": jsonable_encoder(exc.errors())}})

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        """为所有响应补充基础浏览器安全响应头."""
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.get("/api/health", tags=["ops"])
    def health():
        """返回进程存活状态和应用版本,供运维健康检查使用."""
        return {"ok": True, "service": "zio", "version": "0.1.0"}

    @app.get("/api/content-images/{image_id}", tags=["content"])
    def content_image(image_id: str, request: Request, db=Depends(get_db)):
        """按管理员身份或有效公开 Note 权限返回正文图片."""
        if len(image_id) != 32 or any(character not in "0123456789abcdef" for character in image_id):
            raise AppError("image_not_found", "image not found", 404)
        from .services.auth import COOKIE_NAME, current_user

        administrator = current_user(db, request.cookies.get(COOKIE_NAME))
        row = repo.get_content_image(db, image_id, public=administrator is None)
        if row is None:
            raise AppError("image_not_found", "image not found", 404)
        path = resolve_upload(settings.uploads_root, row["storage_path"])
        return FileResponse(
            path,
            media_type=row["media_type"],
            headers={"Cache-Control": "private, no-store" if administrator else "public, max-age=300"},
        )

    @app.get("/page/{note_id}", include_in_schema=True)
    def static_page(note_id: int, request: Request, db=Depends(get_db)):
        """先校验 Note 访问权限,再读取受限静态 HTML,并施加严格 CSP."""
        row = db.execute(f"SELECT n.* FROM notes n WHERE n.id=? AND {repo.PUBLIC_NOTE_SQL}", (note_id,)).fetchone()
        if row is None:
            # 已登录管理员可以读取私密静态页,但访客不能通过猜 URL 确认其存在.
            from .services.auth import COOKIE_NAME, current_user
            if current_user(db, request.cookies.get(COOKIE_NAME)) is None:
                raise AppError("not_found", "static page not found", 404)
            row = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if row is None or not row["static_path"]:
            raise AppError("static_page_not_found", "static page is not available", 404)
        path = resolve_static(settings.static_pages_root, row["static_path"], settings.max_static_page_bytes)
        return FileResponse(
            path,
            media_type="text/html",
            headers={
                "Content-Security-Policy": "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:; script-src 'none'; object-src 'none'; frame-src 'none'; connect-src 'none'; media-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
                "Cache-Control": "no-store" if row["visibility"] == "private" else "public, max-age=60",
            },
        )

    @app.get("/")
    def root():
        """返回前端构建产物的入口页."""
        index = settings.frontend_dist / "index.html"
        if not index.is_file():
            raise AppError("frontend_not_built", "frontend build is not available", 503)
        return FileResponse(index)

    @app.get("/{path:path}")
    def spa_fallback(path: str):
        """为前端路由返回入口页,同时拒绝吞掉 API,静态页和资源路径."""
        if path in {"api", "page", "assets", "media"} or path.startswith(("api/", "page/", "assets/", "media/")):
            raise AppError("not_found", "resource not found", 404)
        index = settings.frontend_dist / "index.html"
        if not index.is_file():
            raise AppError("frontend_not_built", "frontend build is not available", 503)
        return FileResponse(index)

    return app


app = create_app()
