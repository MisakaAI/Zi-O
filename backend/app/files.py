from __future__ import annotations

import os
from pathlib import Path

from .errors import AppError


def resolve_static(root: Path, relative: str, max_bytes: int) -> Path:
    if not relative or relative.startswith("/") or "\\" in relative or "\x00" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise AppError("static_page_not_found", "static page is not available", 404)
    candidate = root / relative
    try:
        root_real = root.resolve(strict=True)
        path_real = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise AppError("static_page_not_found", "static page is not available", 404) from exc
    try:
        path_real.relative_to(root_real)
    except ValueError as exc:
        raise AppError("static_page_not_found", "static page is not available", 404) from exc
    if path_real.suffix.lower() != ".html" or not path_real.is_file():
        raise AppError("static_page_not_found", "static page is not available", 404)
    current = root
    for part in Path(relative).parts:
        current = current / part
        try:
            if current.is_symlink():
                raise AppError("static_page_not_found", "static page is not available", 404)
        except OSError as exc:
            raise AppError("static_page_not_found", "static page is not available", 404) from exc
    try:
        if path_real.stat().st_size > max_bytes:
            raise AppError("static_page_not_found", "static page is not available", 404)
    except OSError as exc:
        raise AppError("static_page_not_found", "static page is not available", 404) from exc
    return path_real


def resolve_cover(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts or "\\" in relative:
        raise AppError("poster_not_found", "poster is not available", 404)
    candidate = root / relative
    try:
        root_real = root.resolve(strict=True)
        path_real = candidate.resolve(strict=True)
        path_real.relative_to(root_real)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        raise AppError("poster_not_found", "poster is not available", 404) from exc
    if not path_real.is_file():
        raise AppError("poster_not_found", "poster is not available", 404)
    return path_real


def safe_remove(root: Path, relative: str | None) -> None:
    if not relative:
        return
    try:
        path = resolve_cover(root, relative)
    except AppError:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
