"""Note,Item,分类,标签,站点设置及其关联关系的业务规则."""

from __future__ import annotations

import json
import re
import sqlite3
from html.parser import HTMLParser
from typing import ClassVar

from ..domain import name_key, normalize_text, slugify, validate_metadata, validate_static_path, validate_timezone
from ..errors import AppError
from ..rendering import linkify_hashtags, render_content
from ..repositories import content as repo
from ..schemas import (
    CategoryLink,
    ItemLink,
    ItemPatch,
    ItemWrite,
    NotePatch,
    NoteWrite,
    SettingsPatch,
    TagPatch,
    TagWrite,
)
from ..timeutil import iso_utc, local_date_key, local_month_bounds, now_ms, parse_utc_ms

_HASHTAG_PATTERN = re.compile(r"(?<![\w#])#([\w]{1,64})(?!\w)", re.UNICODE)
_CONTENT_IMAGE_PATH = re.compile(r"/api/content-images/([0-9a-f]{32})")


class _HashtagTextParser(HTMLParser):
    """提取正文可见文本中的 hashtag,同时跳过代码和脚本节点."""

    _IGNORED_TAGS: ClassVar[frozenset[str]] = frozenset({"code", "pre", "script", "style"})
    _BLOCK_TAGS: ClassVar[frozenset[str]] = frozenset({"address", "blockquote", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p"})

    def __init__(self) -> None:
        """初始化文本缓冲区和被忽略 HTML 深度."""
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """处理开始标签,只为正文块添加换行并跟踪忽略节点."""
        del attrs
        tag = tag.lower()
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
        elif self._ignored_depth == 0 and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """处理自闭合标签,并为可视正文块补充换行."""
        del attrs
        if self._ignored_depth == 0 and tag.lower() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """处理结束标签,关闭对应的忽略深度或正文块换行."""
        tag = tag.lower()
        if tag in self._IGNORED_TAGS:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        elif self._ignored_depth == 0 and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        """收集非代码节点中的可见文本,供 hashtag 识别."""
        if self._ignored_depth == 0:
            self.parts.append(data)


def _hashtag_names(content_raw: str) -> list[str]:
    """从正文可见文本提取去重后的 hashtag 显示名称."""
    parser = _HashtagTextParser()
    parser.feed(content_raw)
    parser.close()
    text = "".join(parser.parts)
    names: list[str] = []
    seen: set[str] = set()
    for match in _HASHTAG_PATTERN.finditer(text):
        name = match.group(1)
        key = name_key(name)
        if key not in seen:
            names.append(name)
            seen.add(key)
    return names


class _ContentImageParser(HTMLParser):
    """从正文 HTML 的 img src 中提取受管理的正文图片 ID."""

    def __init__(self) -> None:
        """初始化去重后的图片 ID 缓冲区."""
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """只处理 img 标签,并识别符合受管理 URL 格式的 src."""
        if tag.lower() != "img":
            return
        source = next((value for name, value in attrs if name.lower() == "src"), None)
        if source:
            match = _CONTENT_IMAGE_PATH.fullmatch(source)
            if match and match.group(1) not in self.ids:
                self.ids.append(match.group(1))

    handle_startendtag = handle_starttag


def _content_image_ids(db: sqlite3.Connection, content_raw: str) -> list[str]:
    """提取正文图片 ID,并确认每个 ID 已在数据库登记后才允许关联."""
    parser = _ContentImageParser()
    parser.feed(content_raw)
    parser.close()
    if parser.ids:
        placeholders = ",".join("?" for _ in parser.ids)
        found = {
            row["id"]
            for row in db.execute(f"SELECT id FROM content_images WHERE id IN ({placeholders})", parser.ids).fetchall()
        }
        # 正文引用不存在的图片会造成永远无法访问的链接,因此保存前拒绝它.
        if found != set(parser.ids):
            raise AppError("image_not_found", "one or more content images do not exist", 422)
    return parser.ids


def _required_row(row: sqlite3.Row | None, code: str, message: str) -> sqlite3.Row:
    """断言查询结果存在,不存在时抛出统一的资源未找到错误."""
    if row is None:
        raise AppError(code, message, 404)
    return row


def _parse_time(value: str | int | float, field: str) -> int:
    """解析并限制单个时间字段,转换底层异常为稳定 API 错误."""
    try:
        result = parse_utc_ms(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise AppError("invalid_timestamp", f"{field} must be a UTC ISO timestamp", 422) from exc
    if result < -62135596800000 or result > 253402300799999:
        raise AppError("invalid_timestamp", f"{field} is out of range", 422)
    return result


def _category_links(db: sqlite3.Connection, links: list[CategoryLink] | None) -> list[tuple[int, int]]:
    """校验 Note 分类关联,并确保恰好一个主分类;未传时默认 JOURNAL."""
    if not links:
        journal = db.execute("SELECT id FROM categories WHERE code='JOURNAL'").fetchone()
        return [(journal["id"], 1)]
    ids = [link.category_id for link in links]
    if len(ids) != len(set(ids)):
        raise AppError("duplicate_category", "a category may only appear once", 422)
    primary = [link.category_id for link in links if link.is_primary]
    if len(primary) != 1:
        raise AppError("primary_category_required", "exactly one category must be primary", 422)
    found = {row["id"] for row in db.execute(f"SELECT id FROM categories WHERE id IN ({','.join('?' for _ in ids)})", ids).fetchall()}
    if found != set(ids):
        raise AppError("category_not_found", "one or more categories do not exist", 422)
    return [(link.category_id, int(link.is_primary)) for link in links]


def _item_links(db: sqlite3.Connection, links: list[ItemLink] | None) -> list[ItemLink]:
    """校验 Note 的 Item 关联 ID 唯一且全部存在."""
    links = links or []
    ids = [link.item_id for link in links]
    if len(ids) != len(set(ids)):
        raise AppError("duplicate_item", "an item may only appear once", 422)
    if ids:
        found = {row["id"] for row in db.execute(f"SELECT id FROM items WHERE id IN ({','.join('?' for _ in ids)})", ids).fetchall()}
        if found != set(ids):
            raise AppError("item_not_found", "one or more items do not exist", 422)
    return links


def _tag_ids(db: sqlite3.Connection, tag_ids: list[int] | None) -> list[int]:
    """校验显式标签 ID 唯一且全部存在."""
    ids = tag_ids or []
    if len(ids) != len(set(ids)):
        raise AppError("duplicate_tag", "a tag may only appear once", 422)
    if ids:
        found = {row["id"] for row in db.execute(f"SELECT id FROM tags WHERE id IN ({','.join('?' for _ in ids)})", ids).fetchall()}
        if found != set(ids):
            raise AppError("tag_not_found", "one or more tags do not exist", 422)
    return ids


def _merge_tag_ids(*groups: list[int]) -> list[int]:
    """按传入顺序合并多组标签 ID,并去除重复项."""
    ids: list[int] = []
    seen: set[int] = set()
    for group in groups:
        for tag_id in group:
            if tag_id not in seen:
                ids.append(tag_id)
                seen.add(tag_id)
    return ids


def _insert_tag(db: sqlite3.Connection, display: str, *, reject_duplicate: bool) -> int:
    """复用或创建标签,并为冲突 slug 追加递增后缀."""
    key = name_key(display)
    existing = db.execute("SELECT id FROM tags WHERE name_key=?", (key,)).fetchone()
    if existing:
        if reject_duplicate:
            raise AppError("duplicate_tag", "tag name already exists", 409)
        return existing["id"]
    base = slugify(display)
    slug = base
    suffix = 2
    while db.execute("SELECT 1 FROM tags WHERE slug=?", (slug,)).fetchone():
        # slug 不能因重命名或同音名称覆盖已有 URL,因此使用稳定的数字后缀.
        slug = f"{base}-{suffix}"
        suffix += 1
    stamp = now_ms()
    cursor = db.execute("INSERT INTO tags(name,name_key,slug,created_at,updated_at) VALUES(?,?,?,?,?)", (display, key, slug, stamp, stamp))
    return cursor.lastrowid


def _content_tag_ids(db: sqlite3.Connection, content_raw: str) -> list[int]:
    """把正文 hashtag 转为标签 ID,自动复用已有标签."""
    return [_insert_tag(db, name, reject_duplicate=False) for name in _hashtag_names(content_raw)]


def _ensure_public_links(db: sqlite3.Connection, note_id: int, visibility: str, links: list[ItemLink]) -> None:
    """阻止公开 Note 关联私密 Item,维护公共读取的权限不变量."""
    if visibility != "public" or not links:
        return
    ids = [link.item_id for link in links]
    placeholders = ",".join("?" for _ in ids)
    private = db.execute(f"SELECT id FROM items WHERE id IN ({placeholders}) AND visibility='private'", ids).fetchall()
    if private:
        raise AppError("private_item_link", "a public note cannot be linked to a private item", 409, {"item_ids": [row["id"] for row in private]})


def _replace_note_links(db: sqlite3.Connection, note_id: int, categories: list[tuple[int, int]], items: list[ItemLink], tags: list[int]) -> None:
    """完整替换 Note 的分类,Item 和标签关联,调用方负责包裹事务."""
    db.execute("DELETE FROM note_categories WHERE note_id=?", (note_id,))
    db.executemany("INSERT INTO note_categories(note_id, category_id, is_primary) VALUES (?, ?, ?)", [(note_id, cid, primary) for cid, primary in categories])
    db.execute("DELETE FROM note_items WHERE note_id=?", (note_id,))
    db.executemany(
        "INSERT INTO note_items(note_id, item_id, context_label, progress_text) VALUES (?, ?, ?, ?)",
        [(note_id, item.item_id, item.context_label, item.progress_text) for item in items],
    )
    db.execute("DELETE FROM note_tags WHERE note_id=?", (note_id,))
    db.executemany("INSERT INTO note_tags(note_id, tag_id) VALUES (?, ?)", [(note_id, tag_id) for tag_id in tags])


def _replace_note_images(db: sqlite3.Connection, note_id: int, image_ids: list[str]) -> None:
    """完整替换 Note 的正文图片关联,调用方负责先完成图片存在性校验."""
    db.execute("DELETE FROM note_images WHERE note_id=?", (note_id,))
    db.executemany("INSERT INTO note_images(note_id, image_id) VALUES (?, ?)", [(note_id, image_id) for image_id in image_ids])


def note_dict(db: sqlite3.Connection, row: sqlite3.Row, *, include_raw: bool) -> dict:
    """把 Note 数据库行转换为 API 对象,并只输出已清理的 HTML."""
    tags = [{"id": tag["id"], "name": tag["name"], "slug": tag["slug"]} for tag in repo.tags_for_note(db, row["id"])]
    result = {
        "id": row["id"],
        "archive_no": row["archive_no"],
        "archive_label": f"LOG/{row['archive_no']:06d}",
        "title": row["title"],
        "content_html_sanitized": linkify_hashtags(render_content(row["content_raw"]), tags),
        "started_at": iso_utc(row["started_at"]),
        "ended_at": iso_utc(row["ended_at"]),
        "visibility": row["visibility"],
        "has_static_page": bool(row["static_path"]),
        "created_at": iso_utc(row["created_at"]),
        "updated_at": iso_utc(row["updated_at"]),
        "categories": [
            {"id": item["id"], "code": item["code"], "name": item["name"], "is_primary": bool(item["is_primary"])}
            for item in repo.categories_for_note(db, row["id"])
        ],
        "items": [
            {
                "id": item["id"], "title": item["title"], "subtitle": item["subtitle"], "creator": item["creator"],
                "visibility": item["visibility"], "category_code": item["category_code"], "category_name": item["category_name"],
                "context_label": item["context_label"], "progress_text": item["progress_text"],
            }
            for item in repo.items_for_note(db, row["id"])
        ],
        "tags": tags,
    }
    if include_raw:
        result["content_raw"] = row["content_raw"]
        result["static_path"] = row["static_path"]
    elif row["static_path"]:
        result["static_url"] = f"/page/{row['id']}"
    return result


def public_calendar(db: sqlite3.Connection, year: int, month: int, timezone_name: str) -> list[dict]:
    """按站点时区聚合指定月份的有效公开 Note 数量."""
    start_ms, end_ms = local_month_bounds(year, month, timezone_name)
    counts: dict[str, int] = {}
    for row in repo.public_calendar_starts(db, start_ms, end_ms):
        date_key = local_date_key(row["started_at"], timezone_name)
        counts[date_key] = counts.get(date_key, 0) + 1
    return [{"date": date_key, "count": counts[date_key]} for date_key in sorted(counts)]


def item_dict(db: sqlite3.Connection, row: sqlite3.Row, *, public: bool) -> dict:
    """把 Item 数据库行转换为 API 对象,并生成对应权限范围的封面 URL."""
    metadata = json.loads(row["metadata_json"] or "{}")
    result = {
        "id": row["id"], "title": row["title"], "subtitle": row["subtitle"], "creator": row["creator"],
        "category_id": row["category_id"], "category_code": row["category_code"] if "category_code" in row.keys() else None,
        "category_name": row["category_name"] if "category_name" in row.keys() else None,
        "visibility": row["visibility"], "metadata_json": metadata,
        "created_at": iso_utc(row["created_at"]), "updated_at": iso_utc(row["updated_at"]),
        "activity_at": iso_utc(row["activity_at"]) if "activity_at" in row.keys() and row["activity_at"] else None,
    }
    if row["poster_path"]:
        result["poster_url"] = f"/api/{'public' if public else 'manage'}/items/{row['id']}/poster"
    else:
        result["poster_url"] = None
    return result


def create_note(db: sqlite3.Connection, payload: NoteWrite) -> dict:
    """校验并原子创建 Note,archive_no 及其分类/Item/标签/图片关联."""
    started = now_ms() if payload.started_at is None else _parse_time(payload.started_at, "started_at")
    ended = _parse_time(payload.ended_at, "ended_at") if payload.ended_at is not None else None
    if ended is not None and ended < started:
        raise AppError("invalid_interval", "ended_at cannot precede started_at", 422)
    static_path = validate_static_path(payload.static_path)
    categories = _category_links(db, payload.categories)
    items = _item_links(db, payload.items)
    explicit_tags = _tag_ids(db, payload.tag_ids)
    _ensure_public_links(db, 0, payload.visibility, items)
    title = normalize_text(payload.title, 200, "title")
    content = normalize_text(payload.content_raw, 1_048_576, "content_raw")
    timestamp = now_ms()
    # archive_no 和所有关联必须在同一事务内分配,才能保证编号只增不重且不留下半成品.
    db.execute("BEGIN IMMEDIATE")
    try:
        tags = _merge_tag_ids(explicit_tags, _content_tag_ids(db, content))
        image_ids = _content_image_ids(db, content)
        db.execute("UPDATE counters SET value=value+1 WHERE name='archive_no'")
        archive_no = db.execute("SELECT value FROM counters WHERE name='archive_no'").fetchone()["value"]
        cursor = db.execute(
            """INSERT INTO notes(archive_no,title,content_raw,started_at,ended_at,visibility,static_path,created_at,updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (archive_no, title, content, started, ended, payload.visibility, static_path, timestamp, timestamp),
        )
        note_id = cursor.lastrowid
        _replace_note_links(db, note_id, categories, items, tags)
        _replace_note_images(db, note_id, image_ids)
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return note_dict(db, _required_row(repo.get_note(db, note_id), "note_not_found", "note was not created"), include_raw=True)


def update_note(db: sqlite3.Connection, note_id: int, payload: NotePatch) -> dict:
    """部分更新 Note,并在需要时原子替换其关联和正文图片."""
    current = _required_row(repo.get_note(db, note_id), "note_not_found", "note not found",)
    data = payload.model_dump(exclude_unset=True)
    started = _parse_time(data["started_at"], "started_at") if "started_at" in data and data["started_at"] is not None else current["started_at"]
    ended = _parse_time(data["ended_at"], "ended_at") if "ended_at" in data and data["ended_at"] is not None else (None if "ended_at" in data else current["ended_at"])
    if ended is not None and ended < started:
        raise AppError("invalid_interval", "ended_at cannot precede started_at", 422)
    visibility = data.get("visibility", current["visibility"])
    categories = _category_links(db, payload.categories) if "categories" in data else None
    items = _item_links(db, payload.items) if "items" in data else None
    explicit_tags = _tag_ids(db, payload.tag_ids) if "tag_ids" in data else None
    if items is not None:
        _ensure_public_links(db, note_id, visibility, items)
    elif visibility == "public":
        private = db.execute("""SELECT i.id FROM items i JOIN note_items ni ON ni.item_id=i.id WHERE ni.note_id=? AND i.visibility='private'""", (note_id,)).fetchall()
        if private:
            raise AppError("private_item_link", "a public note cannot be linked to a private item", 409)
    static_path = validate_static_path(data["static_path"]) if "static_path" in data else current["static_path"]
    content = normalize_text(data["content_raw"], 1_048_576, "content_raw") if "content_raw" in data else current["content_raw"]
    tags = None
    values = {
        "title": normalize_text(data["title"], 200, "title") if "title" in data else current["title"],
        "content_raw": content,
        "started_at": started, "ended_at": ended, "visibility": visibility, "static_path": static_path, "updated_at": now_ms(),
    }
    # 先在事务内更新正文和所有关联,失败时回滚,避免 Note 与标签/图片状态不一致.
    db.execute("BEGIN IMMEDIATE")
    try:
        if "content_raw" in data:
            tags = _merge_tag_ids(explicit_tags or [], _content_tag_ids(db, content))
        elif explicit_tags is not None:
            tags = explicit_tags
        db.execute(
            """UPDATE notes SET title=?,content_raw=?,started_at=?,ended_at=?,visibility=?,static_path=?,updated_at=? WHERE id=?""",
            (*values.values(), note_id),
        )
        if "content_raw" in data:
            _replace_note_images(db, note_id, _content_image_ids(db, content))
        if categories is not None or items is not None or tags is not None:
            old_categories = [(row["id"], int(row["is_primary"])) for row in repo.categories_for_note(db, note_id)]
            old_items = [ItemLink(item_id=row["id"], context_label=row["context_label"], progress_text=row["progress_text"]) for row in repo.items_for_note(db, note_id)]
            old_tags = [row["id"] for row in repo.tags_for_note(db, note_id)]
            _replace_note_links(db, note_id, categories or old_categories, items if items is not None else old_items, tags if tags is not None else old_tags)
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return note_dict(db, _required_row(repo.get_note(db, note_id), "note_not_found", "note not found"), include_raw=True)


def delete_note(db: sqlite3.Connection, note_id: int) -> None:
    """删除 Note;关联表由 SQLite 外键 CASCADE 自动清理."""
    _required_row(repo.get_note(db, note_id), "note_not_found", "note not found")
    db.execute("DELETE FROM notes WHERE id=?", (note_id,))


def create_item(db: sqlite3.Connection, payload: ItemWrite) -> dict:
    """校验根分类和分类专属元数据后创建 Item."""
    category = _required_row(repo.get_category(db, payload.category_id), "category_not_found", "category not found",)
    if not category["is_root"] or category["parent_id"] is not None:
        raise AppError("invalid_item_category", "Item category must be a root category", 422)
    metadata = validate_metadata(category["code"], payload.metadata_json)
    timestamp = now_ms()
    cursor = db.execute(
        """INSERT INTO items(category_id,title,subtitle,creator,visibility,metadata_json,created_at,updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (payload.category_id, normalize_text(payload.title, 200, "title", allow_empty=False), normalize_text(payload.subtitle, 300, "subtitle"), normalize_text(payload.creator, 200, "creator"), payload.visibility, metadata, timestamp, timestamp),
    )
    row = db.execute("""SELECT i.*,c.code AS category_code,c.name AS category_name FROM items i JOIN categories c ON c.id=i.category_id WHERE i.id=?""", (cursor.lastrowid,)).fetchone()
    return item_dict(db, row, public=False)


def update_item(db: sqlite3.Connection, item_id: int, payload: ItemPatch) -> dict:
    """部分更新 Item,并依据变更后的根分类重新校验元数据."""
    current = _required_row(repo.get_item(db, item_id), "item_not_found", "item not found")
    data = payload.model_dump(exclude_unset=True)
    category_id = data.get("category_id", current["category_id"])
    category = _required_row(repo.get_category(db, category_id), "category_not_found", "category not found")
    if not category["is_root"] or category["parent_id"] is not None:
        raise AppError("invalid_item_category", "Item category must be a root category", 422)
    metadata = validate_metadata(category["code"], data.get("metadata_json", json.loads(current["metadata_json"] or "{}")))
    values = (
        category_id, data.get("title", current["title"]), data.get("subtitle", current["subtitle"]),
        data.get("creator", current["creator"]), metadata, now_ms(), item_id,
    )
    db.execute("UPDATE items SET category_id=?,title=?,subtitle=?,creator=?,metadata_json=?,updated_at=? WHERE id=?", values)
    row = db.execute("""SELECT i.*,c.code AS category_code,c.name AS category_name FROM items i JOIN categories c ON c.id=i.category_id WHERE i.id=?""", (item_id,)).fetchone()
    return item_dict(db, row, public=False)


def delete_item(db: sqlite3.Connection, item_id: int) -> str | None:
    """删除 Item 并返回旧封面路径,文件清理由 API 层执行."""
    row = _required_row(repo.get_item(db, item_id), "item_not_found", "item not found")
    old_path = row["poster_path"]
    db.execute("DELETE FROM items WHERE id=?", (item_id,))
    return old_path


def change_item_visibility(db: sqlite3.Connection, item_id: int, visibility: str) -> dict:
    """原子变更 Item 可见性;私密化同时强制私密化所有关联 Note."""
    _required_row(repo.get_item(db, item_id), "item_not_found", "item not found")
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("UPDATE items SET visibility=?,updated_at=? WHERE id=?", (visibility, now_ms(), item_id))
        if visibility == "private":
            # 公开化不反向传播;私密化必须传播,确保旧的公开链接立即失效.
            db.execute("UPDATE notes SET visibility='private',updated_at=? WHERE id IN (SELECT note_id FROM note_items WHERE item_id=?)", (now_ms(), item_id))
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    remaining = db.execute("SELECT COUNT(*) AS count FROM notes n JOIN note_items ni ON ni.note_id=n.id WHERE ni.item_id=? AND n.visibility='private'", (item_id,)).fetchone()["count"]
    return {"item_id": item_id, "visibility": visibility, "private_note_count": remaining}


def set_item_notes_public(db: sqlite3.Connection, item_id: int) -> dict:
    """显式公开关联 Note,并跳过仍关联其他私密 Item 的 Note."""
    item = _required_row(repo.get_item(db, item_id), "item_not_found", "item not found")
    if item["visibility"] != "public":
        raise AppError("private_item", "make the Item public before publishing its Notes", 409)
    db.execute("BEGIN IMMEDIATE")
    try:
        candidates = db.execute("SELECT n.id FROM notes n JOIN note_items ni ON ni.note_id=n.id WHERE ni.item_id=? AND n.visibility='private'", (item_id,)).fetchall()
        updated = 0
        blocked: list[int] = []
        for candidate in candidates:
            # 一个 Note 可能关联多个 Item,只有全部 Item 公开时才允许公开它.
            private = db.execute("""SELECT 1 FROM note_items ni JOIN items i ON i.id=ni.item_id WHERE ni.note_id=? AND i.visibility='private'""", (candidate["id"],)).fetchone()
            if private:
                blocked.append(candidate["id"])
            else:
                db.execute("UPDATE notes SET visibility='public',updated_at=? WHERE id=?", (now_ms(), candidate["id"]))
                updated += 1
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return {"item_id": item_id, "updated_count": updated, "blocked_note_ids": blocked, "blocked_count": len(blocked)}


def create_category(db: sqlite3.Connection, name: str, parent_id: int) -> dict:
    """在根分类下创建子分类,并生成不冲突的内部 code."""
    parent = _required_row(repo.get_category(db, parent_id), "category_not_found", "parent category not found")
    if not parent["is_root"] or parent["parent_id"] is not None:
        raise AppError("invalid_parent_category", "a category can only be a child of a root", 422)
    name = normalize_text(name, 100, "name", allow_empty=False)
    base = "custom-" + slugify(name)
    code = base
    suffix = 2
    while db.execute("SELECT 1 FROM categories WHERE code=?", (code,)).fetchone():
        code = f"{base}-{suffix}"
        suffix += 1
    stamp = now_ms()
    cur = db.execute("INSERT INTO categories(code,name,parent_id,is_root,sort_order,created_at,updated_at) VALUES(?,?,?,0,0,?,?)", (code, name, parent_id, stamp, stamp))
    return dict(_required_row(repo.get_category(db, cur.lastrowid), "category_not_found", "category not found"))


def update_category(db: sqlite3.Connection, category_id: int, name: str) -> dict:
    """修改非根分类名称;根分类是系统稳定分类,不允许修改."""
    row = _required_row(repo.get_category(db, category_id), "category_not_found", "category not found")
    if row["is_root"]:
        raise AppError("root_category_immutable", "root categories cannot be changed", 409)
    db.execute("UPDATE categories SET name=?,updated_at=? WHERE id=?", (normalize_text(name, 100, "name", allow_empty=False), now_ms(), category_id))
    return dict(_required_row(repo.get_category(db, category_id), "category_not_found", "category not found"))


def delete_category(db: sqlite3.Connection, category_id: int) -> None:
    """删除未被 Note 或 Item 使用的非根分类."""
    row = _required_row(repo.get_category(db, category_id), "category_not_found", "category not found")
    if row["is_root"]:
        raise AppError("root_category_immutable", "root categories cannot be deleted", 409)
    used = db.execute("SELECT 1 FROM note_categories WHERE category_id=? UNION SELECT 1 FROM items WHERE category_id=?", (category_id, category_id)).fetchone()
    if used:
        raise AppError("category_in_use", "category is still used", 409)
    db.execute("DELETE FROM categories WHERE id=?", (category_id,))


def create_tag(db: sqlite3.Connection, payload: TagWrite) -> dict:
    """创建普通标签并返回其持久化名称,名称键和 slug."""
    display = normalize_text(payload.name, 64, "name", allow_empty=False)
    tag_id = _insert_tag(db, display, reject_duplicate=True)
    return dict(_required_row(repo.get_tag(db, tag_id), "tag_not_found", "tag not found"))


def update_tag(db: sqlite3.Connection, tag_id: int, payload: TagPatch) -> dict:
    """修改普通标签名称,并拒绝与其他标签的规范化名称冲突."""
    _required_row(repo.get_tag(db, tag_id), "tag_not_found", "tag not found")
    display = normalize_text(payload.name, 64, "name", allow_empty=False)
    key = name_key(display)
    conflict = db.execute("SELECT 1 FROM tags WHERE name_key=? AND id<>?", (key, tag_id)).fetchone()
    if conflict:
        raise AppError("duplicate_tag", "tag name already exists", 409)
    db.execute("UPDATE tags SET name=?,name_key=?,updated_at=? WHERE id=?", (display, key, now_ms(), tag_id))
    return dict(_required_row(repo.get_tag(db, tag_id), "tag_not_found", "tag not found"))


def delete_tag(db: sqlite3.Connection, tag_id: int) -> None:
    """删除普通标签及其外键 CASCADE 关联."""
    _required_row(repo.get_tag(db, tag_id), "tag_not_found", "tag not found")
    db.execute("DELETE FROM tags WHERE id=?", (tag_id,))


def settings_dict(db: sqlite3.Connection, *, public: bool) -> dict:
    """按访问范围返回站点设置;公共响应只包含清理后的 About HTML."""
    row = repo.setting_row(db)
    result = {"site_title": row["site_title"], "site_tagline": row["site_tagline"], "timezone": row["timezone"], "now_status": row["now_status"]}
    if public:
        result["about_html_sanitized"] = render_content(row["about_raw"], row["about_format"])
    else:
        result.update({"about_raw": row["about_raw"], "about_format": row["about_format"], "current_note_id": row["current_note_id"]})
    return result


def update_settings(db: sqlite3.Connection, payload: SettingsPatch) -> dict:
    """部分更新站点设置,并校验时区及当前 signal Note 是否存在."""
    current = repo.setting_row(db)
    data = payload.model_dump(exclude_unset=True)
    if "timezone" in data:
        validate_timezone(data["timezone"])
    if "current_note_id" in data and data["current_note_id"] is not None:
        _required_row(repo.get_note(db, data["current_note_id"]), "note_not_found", "current Note not found")
    columns = ["site_title", "site_tagline", "timezone", "now_status", "about_raw", "about_format", "current_note_id"]
    values = [data.get(column, current[column]) for column in columns]
    db.execute("UPDATE settings SET site_title=?,site_tagline=?,timezone=?,now_status=?,about_raw=?,about_format=?,current_note_id=?,updated_at=? WHERE id=1", (*values, now_ms()))
    return settings_dict(db, public=False)
