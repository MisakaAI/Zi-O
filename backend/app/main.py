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
from .db.migrations import migrate
from .db.connection import connect
from .errors import AppError
from .files import resolve_static
from .repositories import content as repo
from .services import content as service


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_directories()
    migrate(settings.database_path, Path(__file__).parents[1] / "migrations")
    # Apply the environment timezone only to a freshly seeded settings row;
    # subsequent administrator changes remain authoritative.
    with connect(settings.database_path) as db:
        row = db.execute("SELECT timezone, updated_at FROM settings WHERE id=1").fetchone()
        if row and row["updated_at"] == 0 and row["timezone"] != settings.timezone:
            db.execute("UPDATE settings SET timezone=? WHERE id=1", (settings.timezone,))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
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
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message, **({"details": exc.details} if exc.details is not None else {})}})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "request validation failed", "details": jsonable_encoder(exc.errors())}})

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.get("/api/health", tags=["ops"])
    def health():
        return {"ok": True, "service": "zio", "version": "0.1.0"}

    @app.get("/page/{note_id}", include_in_schema=True)
    def static_page(note_id: int, request: Request, db=Depends(get_db)):
        row = db.execute(f"SELECT n.* FROM notes n WHERE n.id=? AND {repo.PUBLIC_NOTE_SQL}", (note_id,)).fetchone()
        if row is None:
            # An authenticated administrator may read private static pages.
            from .services.auth import current_user, COOKIE_NAME
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
        index = settings.frontend_dist / "index.html"
        if not index.is_file():
            raise AppError("frontend_not_built", "frontend build is not available", 503)
        return FileResponse(index)

    @app.get("/{path:path}")
    def spa_fallback(path: str):
        if path in {"api", "page", "assets", "media"} or path.startswith(("api/", "page/", "assets/", "media/")):
            raise AppError("not_found", "resource not found", 404)
        index = settings.frontend_dist / "index.html"
        if not index.is_file():
            raise AppError("frontend_not_built", "frontend build is not available", 503)
        return FileResponse(index)

    return app


app = create_app()
