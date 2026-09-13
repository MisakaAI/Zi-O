from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse

from ..errors import AppError
from ..files import resolve_cover
from ..repositories import content as repo
from ..security import make_cursor, read_cursor
from ..services import content as service
from ..timeutil import iso_utc, local_day_start_ms, now_ms
from .deps import get_db

router = APIRouter(prefix="/api/public", tags=["public"])


def _cursor_scope(cursor: str | None, scope: dict, secret: bytes) -> tuple[int, int] | None:
    if not cursor:
        return None
    try:
        payload = read_cursor(cursor, secret)
    except ValueError as exc:
        raise AppError("cursor_invalid", "cursor is invalid", 400) from exc
    if payload.get("scope") != scope:
        raise AppError("cursor_scope_mismatch", "cursor does not match this query", 400)
    try:
        return int(payload["started_at"]), int(payload["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError("cursor_invalid", "cursor is invalid", 400) from exc


def _unique_tag_slugs(values: list[str] | None) -> list[str]:
    slugs: list[str] = []
    for value in values or []:
        if len(value) > 128:
            raise AppError("invalid_input", "tag slug is too long", 422)
        if value and value not in slugs:
            slugs.append(value)
    return slugs


def _timeline_response(db, request: Request, *, category_code=None, tag_slugs=None, item_id=None, cursor=None, limit=20):
    tag_slugs = _unique_tag_slugs(tag_slugs)
    scope = {"category": category_code, "tags": tag_slugs, "item": item_id}
    position = _cursor_scope(cursor, scope, request.app.state.settings.secret_key)
    rows = repo.timeline_rows(
        db,
        public=True,
        limit=limit + 1,
        cursor=position,
        category_code=category_code,
        tag_slugs=tag_slugs,
        item_id=item_id,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = make_cursor({"v": 1, "scope": scope, "started_at": last["started_at"], "id": last["id"]}, request.app.state.settings.secret_key)
    return {"items": [service.note_dict(db, row, include_raw=False) for row in rows], "next_cursor": next_cursor}


@router.get("/site")
def site(db=Depends(get_db)):
    return service.settings_dict(db, public=True)


@router.get("/now")
def now(request: Request, db=Depends(get_db)):
    stamp = now_ms()
    settings = repo.setting_row(db)
    signal = None
    if settings["current_note_id"]:
        candidate = db.execute(f"SELECT n.* FROM notes n WHERE n.id=? AND {repo.PUBLIC_NOTE_SQL}", (settings["current_note_id"],)).fetchone()
        if candidate:
            signal = service.note_dict(db, candidate, include_raw=False)
    day_start = local_day_start_ms(stamp, settings["timezone"])
    recent_rows = repo.timeline_rows(db, public=True, limit=6, category_code=None, tag_slugs=None, item_id=None, before_ms=stamp)
    today = [row for row in recent_rows if row["started_at"] >= day_start and row["started_at"] <= stamp]
    chosen = today or [row for row in recent_rows if row["started_at"] <= stamp][:5]
    if signal:
        chosen = [row for row in chosen if row["id"] != signal["id"]]
    return {
        "server_now": iso_utc(stamp), "timezone": settings["timezone"], "status": settings["now_status"],
        "current_signal": signal, "recent_mode": "today" if today else "recent",
        "recent_notes": [service.note_dict(db, row, include_raw=False) for row in chosen],
    }


@router.get("/calendar")
def calendar(
    year: int = Query(..., ge=1, le=9998),
    month: int = Query(..., ge=1, le=12),
    db=Depends(get_db),
):
    settings = repo.setting_row(db)
    return {"year": year, "month": month, "days": service.public_calendar(db, year, month, settings["timezone"])}


@router.get("/timeline")
def timeline(
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    category: str | None = Query(default=None, max_length=80),
    tag: list[str] | None = Query(default=None),
    item_id: int | None = Query(default=None, gt=0),
    db=Depends(get_db),
):
    return _timeline_response(db, request, category_code=category, tag_slugs=tag, item_id=item_id, cursor=cursor, limit=limit)


@router.get("/notes/{note_id}")
def note(note_id: int, db=Depends(get_db)):
    row = db.execute(f"SELECT n.* FROM notes n WHERE n.id=? AND {repo.PUBLIC_NOTE_SQL}", (note_id,)).fetchone()
    if not row:
        raise AppError("not_found", "Note not found", 404)
    return service.note_dict(db, row, include_raw=False)


@router.get("/items")
def items(category: str | None = Query(default=None, max_length=80), db=Depends(get_db)):
    return {"items": [service.item_dict(db, row, public=True) for row in repo.public_items(db, category)]}


@router.get("/items/{item_id}")
def item(item_id: int, request: Request, cursor: str | None = None, limit: int = Query(default=20, ge=1, le=50), db=Depends(get_db)):
    row = db.execute(f"""SELECT i.*,c.code AS category_code,c.name AS category_name,
      COALESCE((SELECT MAX(n.started_at) FROM notes n JOIN note_items ni ON ni.note_id=n.id WHERE ni.item_id=i.id AND {repo.PUBLIC_NOTE_SQL}),i.created_at) AS activity_at
      FROM items i JOIN categories c ON c.id=i.category_id WHERE i.id=? AND i.visibility='public'""", (item_id,)).fetchone()
    if not row:
        raise AppError("not_found", "Item not found", 404)
    result = service.item_dict(db, row, public=True)
    result["timeline"] = _timeline_response(db, request, item_id=item_id, cursor=cursor, limit=limit)
    return result


@router.get("/items/{item_id}/poster")
def item_poster(item_id: int, request: Request, db=Depends(get_db)):
    row = db.execute("SELECT poster_path FROM items WHERE id=? AND visibility='public'", (item_id,)).fetchone()
    if not row or not row["poster_path"]:
        raise AppError("not_found", "poster not found", 404)
    path = resolve_cover(request.app.state.settings.covers_root, row["poster_path"])
    return FileResponse(path)


@router.get("/tags/{slug}")
def tag(
    slug: str,
    request: Request,
    tag: list[str] | None = Query(default=None),
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    db=Depends(get_db),
):
    selected_slugs = _unique_tag_slugs([slug, *(tag or [])])
    public_tags = {row["slug"]: row for row in repo.public_tags(db)}
    if any(selected_slug not in public_tags for selected_slug in selected_slugs):
        raise AppError("not_found", "Tag not found", 404)
    result = _timeline_response(db, request, tag_slugs=selected_slugs, cursor=cursor, limit=limit)
    result["tags"] = [
        {"id": public_tags[selected_slug]["id"], "name": public_tags[selected_slug]["name"], "slug": selected_slug}
        for selected_slug in selected_slugs
    ]
    result["tag"] = result["tags"][0]
    return result


@router.get("/index")
def index(db=Depends(get_db)):
    categories = [row for row in repo.public_categories(db) if row["is_root"] or row["note_count"]]
    return {
        "categories": [dict(row) for row in categories],
        "tags": [dict(row) for row in repo.public_tags(db)],
        "items": [service.item_dict(db, row, public=True) for row in repo.public_items(db)],
    }
