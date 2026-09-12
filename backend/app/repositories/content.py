from __future__ import annotations

import json
import sqlite3
from typing import Iterable

from ..timeutil import now_ms


PUBLIC_NOTE_SQL = """n.visibility = 'public'
AND NOT EXISTS (
  SELECT 1 FROM note_items pni
  JOIN items pi ON pi.id = pni.item_id
  WHERE pni.note_id = n.id AND pi.visibility = 'private'
)"""


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def get_note(db: sqlite3.Connection, note_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()


def get_item(db: sqlite3.Connection, item_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def get_category(db: sqlite3.Connection, category_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()


def get_tag(db: sqlite3.Connection, tag_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()


def categories_for_note(db: sqlite3.Connection, note_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """SELECT c.*, nc.is_primary FROM categories c
           JOIN note_categories nc ON nc.category_id = c.id
           WHERE nc.note_id = ? ORDER BY nc.is_primary DESC, c.sort_order, c.id""",
        (note_id,),
    ).fetchall()


def items_for_note(db: sqlite3.Connection, note_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """SELECT i.*, ni.context_label, ni.progress_text, c.code AS category_code, c.name AS category_name
           FROM items i JOIN note_items ni ON ni.item_id = i.id
           JOIN categories c ON c.id = i.category_id
           WHERE ni.note_id = ? ORDER BY i.title COLLATE NOCASE, i.id""",
        (note_id,),
    ).fetchall()


def tags_for_note(db: sqlite3.Connection, note_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """SELECT t.* FROM tags t JOIN note_tags nt ON nt.tag_id = t.id
           WHERE nt.note_id = ? ORDER BY t.name COLLATE NOCASE, t.id""",
        (note_id,),
    ).fetchall()


def timeline_rows(
    db: sqlite3.Connection,
    *,
    public: bool,
    limit: int,
    cursor: tuple[int, int] | None = None,
    category_code: str | None = None,
    tag_slug: str | None = None,
    item_id: int | None = None,
    before_ms: int | None = None,
) -> list[sqlite3.Row]:
    where: list[str] = [PUBLIC_NOTE_SQL if public else "1=1"]
    params: list[object] = []
    if cursor:
        where.append("(n.started_at < ? OR (n.started_at = ? AND n.id < ?))")
        params.extend([cursor[0], cursor[0], cursor[1]])
    if before_ms is not None:
        where.append("n.started_at <= ?")
        params.append(before_ms)
    if category_code:
        where.append("EXISTS (SELECT 1 FROM note_categories qnc JOIN categories qc ON qc.id=qnc.category_id WHERE qnc.note_id=n.id AND qc.code=?)")
        params.append(category_code)
    if tag_slug:
        where.append("EXISTS (SELECT 1 FROM note_tags qnt JOIN tags qt ON qt.id=qnt.tag_id WHERE qnt.note_id=n.id AND qt.slug=?)")
        params.append(tag_slug)
    if item_id:
        where.append("EXISTS (SELECT 1 FROM note_items qni WHERE qni.note_id=n.id AND qni.item_id=?)")
        params.append(item_id)
    params.append(limit)
    return db.execute(
        f"SELECT n.* FROM notes n WHERE {' AND '.join(where)} ORDER BY n.started_at DESC, n.id DESC LIMIT ?",
        params,
    ).fetchall()


def public_item_activity(db: sqlite3.Connection, item_id: int) -> int | None:
    row = db.execute(
        f"""SELECT MAX(n.started_at) AS activity FROM notes n JOIN note_items ni ON ni.note_id=n.id
            WHERE ni.item_id=? AND {PUBLIC_NOTE_SQL}""",
        (item_id,),
    ).fetchone()
    return row["activity"]


def public_items(db: sqlite3.Connection, category_code: str | None = None) -> list[sqlite3.Row]:
    params: list[object] = []
    where = ["i.visibility='public'"]
    if category_code:
        where.append("c.code=?")
        params.append(category_code)
    return db.execute(
        f"""SELECT i.*, c.code AS category_code, c.name AS category_name,
                   COALESCE((SELECT MAX(n.started_at) FROM notes n JOIN note_items ni ON ni.note_id=n.id
                     WHERE ni.item_id=i.id AND {PUBLIC_NOTE_SQL}), i.created_at) AS activity_at
            FROM items i JOIN categories c ON c.id=i.category_id
            WHERE {' AND '.join(where)} ORDER BY activity_at DESC, i.id DESC""",
        params,
    ).fetchall()


def all_categories(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute("SELECT * FROM categories ORDER BY is_root DESC, sort_order, name COLLATE NOCASE, id").fetchall()


def all_tags(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute("SELECT * FROM tags ORDER BY name COLLATE NOCASE, id").fetchall()


def public_tags(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        f"""SELECT t.*, COUNT(DISTINCT n.id) AS note_count FROM tags t
            JOIN note_tags nt ON nt.tag_id=t.id JOIN notes n ON n.id=nt.note_id
            WHERE {PUBLIC_NOTE_SQL} GROUP BY t.id ORDER BY t.name COLLATE NOCASE, t.id"""
    ).fetchall()


def public_categories(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        f"""SELECT c.*, COUNT(DISTINCT n.id) AS note_count FROM categories c
            LEFT JOIN note_categories nc ON nc.category_id=c.id
            LEFT JOIN notes n ON n.id=nc.note_id AND {PUBLIC_NOTE_SQL}
            GROUP BY c.id ORDER BY c.is_root DESC, c.sort_order, c.name COLLATE NOCASE, c.id"""
    ).fetchall()


def setting_row(db: sqlite3.Connection) -> sqlite3.Row:
    return db.execute("SELECT * FROM settings WHERE id=1").fetchone()


def user_by_username(db: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()


def user_by_session(db: sqlite3.Connection, token_hash: bytes, now: int) -> sqlite3.Row | None:
    return db.execute(
        """SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id
           WHERE s.token_hash=? AND s.expires_at>?""",
        (token_hash, now),
    ).fetchone()


def purge_sessions(db: sqlite3.Connection, now: int | None = None) -> None:
    db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now or now_ms(),))
