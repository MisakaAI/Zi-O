from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


@dataclass(frozen=True)
class Settings:
    environment: str
    database_path: Path
    static_pages_root: Path
    covers_root: Path
    frontend_dist: Path
    public_origin: str
    secret_key: bytes
    timezone: str
    cookie_secure: bool
    session_ttl_seconds: int = 7 * 24 * 60 * 60
    max_static_page_bytes: int = 5 * 1024 * 1024
    max_cover_bytes: int = 5 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("ZIO_ENV", "development").lower()
        database_path = _path(os.getenv("ZIO_DATABASE_PATH", "./data/zio.sqlite3"))
        static_pages_root = _path(os.getenv("ZIO_STATIC_PAGES_ROOT", "./data/static-pages"))
        covers_root = _path(os.getenv("ZIO_COVERS_ROOT", "./data/covers"))
        frontend_dist = _path(os.getenv("ZIO_FRONTEND_DIST", "./frontend/dist"))
        origin = os.getenv("ZIO_PUBLIC_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
        raw_secret = os.getenv("ZIO_SECRET_KEY", "dev-only-change-this-secret-key-please")
        secret = raw_secret.encode("utf-8")
        if environment == "production" and len(secret) < 32:
            raise RuntimeError("ZIO_SECRET_KEY must contain at least 32 bytes in production")
        timezone = os.getenv("ZIO_TIMEZONE", "Asia/Shanghai")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise RuntimeError(f"invalid ZIO_TIMEZONE: {timezone}") from exc
        cookie_secure = os.getenv("ZIO_COOKIE_SECURE", "true" if environment == "production" else "false").lower() in {
            "1", "true", "yes", "on"
        }
        return cls(
            environment=environment,
            database_path=database_path,
            static_pages_root=static_pages_root,
            covers_root=covers_root,
            frontend_dist=frontend_dist,
            public_origin=origin,
            secret_key=secret,
            timezone=timezone,
            cookie_secure=cookie_secure,
        )

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.static_pages_root.mkdir(parents=True, exist_ok=True)
        self.covers_root.mkdir(parents=True, exist_ok=True)

