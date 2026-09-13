from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse

from ..errors import AppError
from ..files import resolve_cover, safe_remove
from ..repositories import content as repo
from ..schemas import (
    CategoryPatch,
    CategoryWrite,
    ItemPatch,
    ItemWrite,
    NotePatch,
    NoteWrite,
    SettingsPatch,
    TagPatch,
    TagWrite,
    VisibilityRequest,
)
from ..security import make_cursor, read_cursor
from ..services import content as service
from ..services.auth import public_user
from ..timeutil import now_ms
from .deps import get_db, require_user, require_write_origin

router = APIRouter(prefix="/api/manage", tags=["manage"], dependencies=[Depends(require_user)])

_NOTES_CURSOR_SCOPE = {"resource": "manage_notes"}


def _notes_cursor_position(cursor: str | None, secret: bytes) -> tuple[int, int] | None:
    if not cursor:
        return None
    try:
        payload = read_cursor(cursor, secret)
        if payload.get("scope") != _NOTES_CURSOR_SCOPE:
            raise ValueError("cursor_scope_mismatch")
        return int(payload["started_at"]), int(payload["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError("cursor_invalid", "cursor is invalid", 400) from exc


@router.get("/profile")
def profile(user=Depends(require_user)):
    return {"user": public_user(user)}


@router.get("/settings")
def settings(db=Depends(get_db)):
    return service.settings_dict(db, public=False)


@router.patch("/settings", dependencies=[Depends(require_write_origin)])
def update_settings(payload: SettingsPatch, db=Depends(get_db)):
    return service.update_settings(db, payload)


@router.get("/notes")
def notes(request: Request, cursor: str | None = None, limit: int = Query(default=50, ge=1, le=100), db=Depends(get_db)):
    position = _notes_cursor_position(cursor, request.app.state.settings.secret_key)
    rows = repo.timeline_rows(db, public=False, limit=limit + 1, cursor=position)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = make_cursor(
            {"v": 1, "scope": _NOTES_CURSOR_SCOPE, "started_at": last["started_at"], "id": last["id"]},
            request.app.state.settings.secret_key,
        )
    return {"items": [service.note_dict(db, row, include_raw=True) for row in rows], "next_cursor": next_cursor}


@router.post("/notes", dependencies=[Depends(require_write_origin)])
def create_note(payload: NoteWrite, db=Depends(get_db)):
    return service.create_note(db, payload)


@router.get("/notes/{note_id}")
def get_note(note_id: int, db=Depends(get_db)):
    row = repo.get_note(db, note_id)
    if row is None:
        raise AppError("note_not_found", "note not found", 404)
    return service.note_dict(db, row, include_raw=True)


@router.patch("/notes/{note_id}", dependencies=[Depends(require_write_origin)])
def patch_note(note_id: int, payload: NotePatch, db=Depends(get_db)):
    return service.update_note(db, note_id, payload)


@router.delete("/notes/{note_id}", dependencies=[Depends(require_write_origin)])
def remove_note(note_id: int, db=Depends(get_db)):
    service.delete_note(db, note_id)
    return {"ok": True}


@router.get("/items")
def items(db=Depends(get_db)):
    rows = db.execute("""SELECT i.*,c.code AS category_code,c.name AS category_name,
      COALESCE((SELECT MAX(n.started_at) FROM notes n JOIN note_items ni ON ni.note_id=n.id WHERE ni.item_id=i.id),i.created_at) AS activity_at
      FROM items i JOIN categories c ON c.id=i.category_id ORDER BY activity_at DESC,i.id DESC""").fetchall()
    result = []
    for row in rows:
        item = service.item_dict(db, row, public=False)
        item["private_note_count"] = db.execute("SELECT COUNT(*) AS count FROM notes n JOIN note_items ni ON ni.note_id=n.id WHERE ni.item_id=? AND n.visibility='private'", (row["id"],)).fetchone()["count"]
        result.append(item)
    return {"items": result}


@router.post("/items", dependencies=[Depends(require_write_origin)])
def create_item(payload: ItemWrite, db=Depends(get_db)):
    return service.create_item(db, payload)


@router.get("/items/{item_id}")
def get_item(item_id: int, db=Depends(get_db)):
    row = db.execute("""SELECT i.*,c.code AS category_code,c.name AS category_name,
      COALESCE((SELECT MAX(n.started_at) FROM notes n JOIN note_items ni ON ni.note_id=n.id WHERE ni.item_id=i.id),i.created_at) AS activity_at
      FROM items i JOIN categories c ON c.id=i.category_id WHERE i.id=?""", (item_id,)).fetchone()
    if not row:
        raise AppError("item_not_found", "item not found", 404)
    result = service.item_dict(db, row, public=False)
    result["notes"] = [service.note_dict(db, note, include_raw=False) for note in db.execute("SELECT n.* FROM notes n JOIN note_items ni ON ni.note_id=n.id WHERE ni.item_id=? ORDER BY n.started_at DESC,n.id DESC", (item_id,)).fetchall()]
    result["private_note_count"] = db.execute("SELECT COUNT(*) AS count FROM notes n JOIN note_items ni ON ni.note_id=n.id WHERE ni.item_id=? AND n.visibility='private'", (item_id,)).fetchone()["count"]
    return result


@router.patch("/items/{item_id}", dependencies=[Depends(require_write_origin)])
def patch_item(item_id: int, payload: ItemPatch, db=Depends(get_db)):
    return service.update_item(db, item_id, payload)


@router.delete("/items/{item_id}", dependencies=[Depends(require_write_origin)])
def remove_item(item_id: int, request: Request, db=Depends(get_db)):
    old_path = service.delete_item(db, item_id)
    safe_remove(request.app.state.settings.covers_root, old_path)
    return {"ok": True}


@router.post("/items/{item_id}/visibility", dependencies=[Depends(require_write_origin)])
def item_visibility(item_id: int, payload: VisibilityRequest, db=Depends(get_db)):
    return service.change_item_visibility(db, item_id, payload.visibility)


@router.post("/items/{item_id}/notes/set-public", dependencies=[Depends(require_write_origin)])
def item_notes_public(item_id: int, db=Depends(get_db)):
    return service.set_item_notes_public(db, item_id)


@router.put("/items/{item_id}/poster", dependencies=[Depends(require_write_origin)])
async def upload_poster(item_id: int, request: Request, db=Depends(get_db)):
    row = repo.get_item(db, item_id)
    if row is None:
        raise AppError("item_not_found", "item not found", 404)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    accepted = {"image/png": (b"\x89PNG\r\n\x1a\n", ".png"), "image/jpeg": (b"\xff\xd8\xff", ".jpg"), "image/webp": (b"RIFF", ".webp")}
    if content_type not in accepted:
        raise AppError("invalid_poster", "poster must be PNG, JPEG, or WebP", 415)
    max_bytes = request.app.state.settings.max_cover_bytes
    total = 0
    chunks: list[bytes] = []
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise AppError("poster_too_large", "poster exceeds 5 MiB", 413)
        chunks.append(chunk)
    body = b"".join(chunks)
    signature, extension = accepted[content_type]
    if not body.startswith(signature) or ((content_type == "image/webp" and len(body) < 12) or (content_type == "image/webp" and body[8:12] != b"WEBP")):
        raise AppError("invalid_poster", "poster content does not match its type", 415)
    request.app.state.settings.covers_root.mkdir(parents=True, exist_ok=True)
    relative = f"{uuid.uuid4().hex}{extension}"
    destination = request.app.state.settings.covers_root / relative
    destination.write_bytes(body)
    old_path = row["poster_path"]
    try:
        db.execute("UPDATE items SET poster_path=?,updated_at=? WHERE id=?", (relative, now_ms(), item_id))
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    safe_remove(request.app.state.settings.covers_root, old_path)
    row = db.execute("""SELECT i.*,c.code AS category_code,c.name AS category_name FROM items i JOIN categories c ON c.id=i.category_id WHERE i.id=?""", (item_id,)).fetchone()
    return service.item_dict(db, row, public=False)


@router.delete("/items/{item_id}/poster", dependencies=[Depends(require_write_origin)])
def remove_poster(item_id: int, request: Request, db=Depends(get_db)):
    row = repo.get_item(db, item_id)
    if row is None:
        raise AppError("item_not_found", "item not found", 404)
    db.execute("UPDATE items SET poster_path=NULL,updated_at=? WHERE id=?", (now_ms(), item_id))
    safe_remove(request.app.state.settings.covers_root, row["poster_path"])
    return {"ok": True}


@router.get("/items/{item_id}/poster")
def manage_poster(item_id: int, request: Request, db=Depends(get_db)):
    row = db.execute("SELECT poster_path FROM items WHERE id=?", (item_id,)).fetchone()
    if not row or not row["poster_path"]:
        raise AppError("poster_not_found", "poster not found", 404)
    return FileResponse(resolve_cover(request.app.state.settings.covers_root, row["poster_path"]))


@router.get("/categories")
def categories(db=Depends(get_db)):
    return {"items": [dict(row) for row in repo.all_categories(db)]}


@router.post("/categories", dependencies=[Depends(require_write_origin)])
def create_category(payload: CategoryWrite, db=Depends(get_db)):
    return service.create_category(db, payload.name, payload.parent_id)


@router.patch("/categories/{category_id}", dependencies=[Depends(require_write_origin)])
def patch_category(category_id: int, payload: CategoryPatch, db=Depends(get_db)):
    return service.update_category(db, category_id, payload.name)


@router.delete("/categories/{category_id}", dependencies=[Depends(require_write_origin)])
def remove_category(category_id: int, db=Depends(get_db)):
    service.delete_category(db, category_id)
    return {"ok": True}


@router.get("/tags")
def tags(db=Depends(get_db)):
    return {"items": [dict(row) for row in repo.all_tags(db)]}


@router.post("/tags", dependencies=[Depends(require_write_origin)])
def create_tag(payload: TagWrite, db=Depends(get_db)):
    return service.create_tag(db, payload)


@router.patch("/tags/{tag_id}", dependencies=[Depends(require_write_origin)])
def patch_tag(tag_id: int, payload: TagPatch, db=Depends(get_db)):
    return service.update_tag(db, tag_id, payload)


@router.delete("/tags/{tag_id}", dependencies=[Depends(require_write_origin)])
def remove_tag(tag_id: int, db=Depends(get_db)):
    service.delete_tag(db, tag_id)
    return {"ok": True}
