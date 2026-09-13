"""管理员管理 API,负责请求边界和文件响应,业务规则委托给 service."""

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
# 文件类型既由 Content-Type 初筛,也由文件头复核,避免仅凭请求头保存伪装文件.
_ACCEPTED_IMAGES = {
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/webp": (b"RIFF", ".webp"),
}


async def _read_image(request: Request, *, max_bytes: int, invalid_code: str, too_large_code: str) -> tuple[bytes, str, str]:
    """流式读取并校验上传图片的类型,魔数和大小,返回内容及存储扩展名."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in _ACCEPTED_IMAGES:
        raise AppError(invalid_code, "image must be PNG, JPEG, or WebP", 415)
    total = 0
    chunks: list[bytes] = []
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise AppError(too_large_code, "image exceeds 5 MiB", 413)
        chunks.append(chunk)
    body = b"".join(chunks)
    signature, extension = _ACCEPTED_IMAGES[content_type]
    if not body.startswith(signature) or (content_type == "image/webp" and (len(body) < 12 or body[8:12] != b"WEBP")):
        raise AppError(invalid_code, "image content does not match its type", 415)
    return body, content_type, extension


def _notes_cursor_position(cursor: str | None, secret: bytes) -> tuple[int, int] | None:
    """验证管理端 Note 游标的签名和作用域,并提取联合排序位置."""
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
    """返回当前已鉴权管理员的公开身份."""
    return {"user": public_user(user)}


@router.get("/settings")
def settings(db=Depends(get_db)):
    """返回管理端设置,包括未清理的 About 原文和当前 signal."""
    return service.settings_dict(db, public=False)


@router.patch("/settings", dependencies=[Depends(require_write_origin)])
def update_settings(payload: SettingsPatch, db=Depends(get_db)):
    """更新站点设置,并由服务层校验时区和当前 Note."""
    return service.update_settings(db, payload)


@router.get("/notes")
def notes(request: Request, cursor: str | None = None, limit: int = Query(default=50, ge=1, le=100), db=Depends(get_db)):
    """分页返回全部管理端 Note,包含正文原文和私密记录."""
    position = _notes_cursor_position(cursor, request.app.state.settings.secret_key)
    # 多取一条只用于判断是否还有下一页,响应仍严格遵守客户端请求的 limit.
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
    """创建一条 Note,并由服务层完成关联,标签和正文图片同步."""
    return service.create_note(db, payload)


@router.get("/notes/{note_id}")
def get_note(note_id: int, db=Depends(get_db)):
    """返回管理端可见的单条 Note,包括私密字段和正文原文."""
    row = repo.get_note(db, note_id)
    if row is None:
        raise AppError("note_not_found", "note not found", 404)
    return service.note_dict(db, row, include_raw=True)


@router.patch("/notes/{note_id}", dependencies=[Depends(require_write_origin)])
def patch_note(note_id: int, payload: NotePatch, db=Depends(get_db)):
    """部分更新 Note,并由服务层处理时间,可见性及关联替换."""
    return service.update_note(db, note_id, payload)


@router.delete("/notes/{note_id}", dependencies=[Depends(require_write_origin)])
def remove_note(note_id: int, db=Depends(get_db)):
    """删除 Note 及数据库外键级联的关联记录."""
    service.delete_note(db, note_id)
    return {"ok": True}


@router.get("/items")
def items(db=Depends(get_db)):
    """返回管理端全部 Item,并补充每个 Item 的私密 Note 数量."""
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
    """创建一个 Item,并校验其必须使用根分类."""
    return service.create_item(db, payload)


@router.get("/items/{item_id}")
def get_item(item_id: int, db=Depends(get_db)):
    """返回管理端 Item 详情,全部关联 Note 和私密 Note 数量."""
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
    """更新 Item 的分类,标题,创作者或分类专属元数据."""
    return service.update_item(db, item_id, payload)


@router.delete("/items/{item_id}", dependencies=[Depends(require_write_origin)])
def remove_item(item_id: int, request: Request, db=Depends(get_db)):
    """删除 Item,并在数据库删除成功后清理其旧封面文件."""
    old_path = service.delete_item(db, item_id)
    safe_remove(request.app.state.settings.covers_root, old_path)
    return {"ok": True}


@router.post("/items/{item_id}/visibility", dependencies=[Depends(require_write_origin)])
def item_visibility(item_id: int, payload: VisibilityRequest, db=Depends(get_db)):
    """变更 Item 可见性;私密化时由服务层在同一事务中级联私密化关联 Note."""
    return service.change_item_visibility(db, item_id, payload.visibility)


@router.post("/items/{item_id}/notes/set-public", dependencies=[Depends(require_write_origin)])
def item_notes_public(item_id: int, db=Depends(get_db)):
    """显式公开 Item 的可公开关联 Note,不自动绕过其他私密 Item 的阻断."""
    return service.set_item_notes_public(db, item_id)


@router.put("/items/{item_id}/poster", dependencies=[Depends(require_write_origin)])
async def upload_poster(item_id: int, request: Request, db=Depends(get_db)):
    """上传或替换 Item 封面,并在数据库写入失败时删除新文件."""
    row = repo.get_item(db, item_id)
    if row is None:
        raise AppError("item_not_found", "item not found", 404)
    body, _, extension = await _read_image(
        request,
        max_bytes=request.app.state.settings.max_cover_bytes,
        invalid_code="invalid_poster",
        too_large_code="poster_too_large",
    )
    request.app.state.settings.covers_root.mkdir(parents=True, exist_ok=True)
    relative = f"{uuid.uuid4().hex}{extension}"
    destination = request.app.state.settings.covers_root / relative
    destination.write_bytes(body)
    old_path = row["poster_path"]
    try:
        # 先确保数据库指向新文件,再清理旧文件,避免更新失败导致旧封面丢失.
        db.execute("UPDATE items SET poster_path=?,updated_at=? WHERE id=?", (relative, now_ms(), item_id))
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    safe_remove(request.app.state.settings.covers_root, old_path)
    row = db.execute("""SELECT i.*,c.code AS category_code,c.name AS category_name FROM items i JOIN categories c ON c.id=i.category_id WHERE i.id=?""", (item_id,)).fetchone()
    return service.item_dict(db, row, public=False)


@router.post("/content-images", dependencies=[Depends(require_write_origin)], status_code=201)
async def upload_content_image(request: Request, db=Depends(get_db)):
    """保存正文图片并登记元数据,返回编辑器可嵌入的鉴权图片 URL."""
    body, media_type, extension = await _read_image(
        request,
        max_bytes=request.app.state.settings.max_content_image_bytes,
        invalid_code="invalid_image",
        too_large_code="image_too_large",
    )
    image_id = uuid.uuid4().hex
    relative = f"{image_id}{extension}"
    destination = request.app.state.settings.uploads_root / relative
    request.app.state.settings.uploads_root.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
    try:
        # 图片先落盘,后登记;登记失败时立即回收文件,避免产生孤儿上传.
        db.execute(
            "INSERT INTO content_images(id,storage_path,media_type,created_at) VALUES(?,?,?,?)",
            (image_id, relative, media_type, now_ms()),
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {"id": image_id, "url": f"/api/content-images/{image_id}", "media_type": media_type}


@router.delete("/items/{item_id}/poster", dependencies=[Depends(require_write_origin)])
def remove_poster(item_id: int, request: Request, db=Depends(get_db)):
    """移除 Item 的封面引用,并删除对应的受管理文件."""
    row = repo.get_item(db, item_id)
    if row is None:
        raise AppError("item_not_found", "item not found", 404)
    db.execute("UPDATE items SET poster_path=NULL,updated_at=? WHERE id=?", (now_ms(), item_id))
    safe_remove(request.app.state.settings.covers_root, row["poster_path"])
    return {"ok": True}


@router.get("/items/{item_id}/poster")
def manage_poster(item_id: int, request: Request, db=Depends(get_db)):
    """向已通过路由鉴权的管理员返回 Item 封面文件."""
    row = db.execute("SELECT poster_path FROM items WHERE id=?", (item_id,)).fetchone()
    if not row or not row["poster_path"]:
        raise AppError("poster_not_found", "poster not found", 404)
    return FileResponse(resolve_cover(request.app.state.settings.covers_root, row["poster_path"]))


@router.get("/categories")
def categories(db=Depends(get_db)):
    """返回管理端可维护的全部分类."""
    return {"items": [dict(row) for row in repo.all_categories(db)]}


@router.post("/categories", dependencies=[Depends(require_write_origin)])
def create_category(payload: CategoryWrite, db=Depends(get_db)):
    """创建挂在根分类下的子分类."""
    return service.create_category(db, payload.name, payload.parent_id)


@router.patch("/categories/{category_id}", dependencies=[Depends(require_write_origin)])
def patch_category(category_id: int, payload: CategoryPatch, db=Depends(get_db)):
    """修改非根分类的显示名称."""
    return service.update_category(db, category_id, payload.name)


@router.delete("/categories/{category_id}", dependencies=[Depends(require_write_origin)])
def remove_category(category_id: int, db=Depends(get_db)):
    """删除未被使用的非根分类."""
    service.delete_category(db, category_id)
    return {"ok": True}


@router.get("/tags")
def tags(db=Depends(get_db)):
    """返回管理端全部普通标签."""
    return {"items": [dict(row) for row in repo.all_tags(db)]}


@router.post("/tags", dependencies=[Depends(require_write_origin)])
def create_tag(payload: TagWrite, db=Depends(get_db)):
    """创建一个名称和 slug 均不冲突的普通标签."""
    return service.create_tag(db, payload)


@router.patch("/tags/{tag_id}", dependencies=[Depends(require_write_origin)])
def patch_tag(tag_id: int, payload: TagPatch, db=Depends(get_db)):
    """修改普通标签名称,同时保持名称键唯一."""
    return service.update_tag(db, tag_id, payload)


@router.delete("/tags/{tag_id}", dependencies=[Depends(require_write_origin)])
def remove_tag(tag_id: int, db=Depends(get_db)):
    """删除普通标签及其外键级联关联."""
    service.delete_tag(db, tag_id)
    return {"ok": True}
