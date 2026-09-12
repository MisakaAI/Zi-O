from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.api.manage import notes as manage_notes
from app.db.connection import connect
from app.db.migrations import migrate
from app.errors import AppError
from app.rendering import render_content
from app.schemas import ItemLink, ItemWrite, NotePatch, NoteWrite, TagWrite
from app.services import content
from app.services.auth import create_admin, current_user, login


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = connect(self.root / "test.sqlite3")
        migrate(self.root / "test.sqlite3", Path(__file__).parents[1] / "migrations")

    def tearDown(self):
        self.db.close(); self.temp.cleanup()

    def note(self, **overrides):
        values = {"started_at": "2024-01-01T00:00:00Z", "visibility": "private", "title": "event"}
        values.update(overrides)
        return content.create_note(self.db, NoteWrite(**values))

    def test_migration_and_archive_numbers(self):
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM categories WHERE is_root=1").fetchone()[0], 5)
        first = self.note(); second = self.note(started_at="2020-01-01T00:00:00Z")
        self.assertEqual((first["archive_no"], second["archive_no"]), (1, 2))
        self.db.execute("DELETE FROM notes WHERE id=?", (first["id"],))
        third = self.note()
        self.assertEqual(third["archive_no"], 3)
        migrate(self.root / "test.sqlite3", Path(__file__).parents[1] / "migrations")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0], 1)
        with self.assertRaises(__import__("sqlite3").IntegrityError):
            self.db.execute("INSERT INTO note_items(note_id,item_id) VALUES(999,999)")

    def test_cursor_ordering_query(self):
        self.note(title="one", started_at="2024-01-01T00:00:00Z", visibility="public")
        self.note(title="two", started_at="2024-01-01T00:00:00Z", visibility="public")
        self.note(title="three", started_at="2023-01-01T00:00:00Z", visibility="public")
        rows = __import__("app.repositories.content", fromlist=["timeline_rows"]).timeline_rows(self.db, public=True, limit=2)
        self.assertEqual([row["title"] for row in rows], ["two", "one"])
        rows = __import__("app.repositories.content", fromlist=["timeline_rows"]).timeline_rows(self.db, public=True, limit=2, cursor=(rows[-1]["started_at"], rows[-1]["id"]))
        self.assertEqual([row["title"] for row in rows], ["three"])

    def test_manage_note_cursor_reaches_older_records(self):
        for index in range(51):
            self.note(title=str(index), started_at=f"2024-01-01T00:00:{index:02d}Z")
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(secret_key=b"test-secret")))
        )
        first = manage_notes(request=request, cursor=None, limit=50, db=self.db)
        self.assertEqual(len(first["items"]), 50)
        self.assertIsNotNone(first["next_cursor"])
        second = manage_notes(request=request, cursor=first["next_cursor"], limit=50, db=self.db)
        self.assertEqual([note["title"] for note in second["items"]], ["0"])
        self.assertIsNone(second["next_cursor"])

    def test_item_private_cascade_and_explicit_publish(self):
        book = content.create_item(self.db, ItemWrite(category_id=2, title="Book", visibility="public"))
        note = self.note(items=[ItemLink(item_id=book["id"])])
        content.update_note(self.db, note["id"], NotePatch(visibility="public"))
        content.change_item_visibility(self.db, book["id"], "private")
        self.assertEqual(self.db.execute("SELECT visibility FROM notes WHERE id=?", (note["id"],)).fetchone()[0], "private")
        content.change_item_visibility(self.db, book["id"], "public")
        self.assertEqual(self.db.execute("SELECT visibility FROM notes WHERE id=?", (note["id"],)).fetchone()[0], "private")
        result = content.set_item_notes_public(self.db, book["id"])
        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(self.db.execute("SELECT visibility FROM notes WHERE id=?", (note["id"],)).fetchone()[0], "public")

    def test_public_filter_defense(self):
        public_item = content.create_item(self.db, ItemWrite(category_id=2, title="Visible", visibility="public"))
        private_item = content.create_item(self.db, ItemWrite(category_id=2, title="Hidden", visibility="private"))
        note = self.note(visibility="public", items=[ItemLink(item_id=public_item["id"])])
        self.db.execute("INSERT INTO note_items(note_id,item_id) VALUES(?,?)", (note["id"], private_item["id"]))
        rows = __import__("app.repositories.content", fromlist=["timeline_rows"]).timeline_rows(self.db, public=True, limit=20)
        self.assertEqual(rows, [])

    def test_public_note_rejects_private_item_link(self):
        private_item = content.create_item(self.db, ItemWrite(category_id=2, title="Hidden", visibility="private"))
        with self.assertRaises(AppError) as caught:
            self.note(visibility="public", items=[ItemLink(item_id=private_item["id"])])
        self.assertEqual(caught.exception.code, "private_item_link")

    def test_rendering_removes_xss(self):
        html = render_content('<script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:bad()">x</a>', "html")
        self.assertNotIn("script", html.lower()); self.assertNotIn("onerror", html.lower()); self.assertNotIn("javascript:", html.lower())

    def test_tag_slug_conflict(self):
        first = content.create_tag(self.db, TagWrite(name="Read later")); second = content.create_tag(self.db, TagWrite(name="Read-later"))
        self.assertEqual(first["slug"], "read-later"); self.assertEqual(second["slug"], "read-later-2")

    def test_private_only_tag_is_not_in_public_index(self):
        tag = content.create_tag(self.db, TagWrite(name="Secret tag"))
        note = self.note(tag_ids=[tag["id"]], visibility="private")
        rows = __import__("app.repositories.content", fromlist=["public_tags"]).public_tags(self.db)
        self.assertEqual(rows, [])

    def test_password_and_session(self):
        create_admin(self.db, "misaka", "secret123")
        token, user = login(self.db, "misaka", "secret123", 100)
        self.assertTrue(token); self.assertEqual(user["username"], "misaka")
        with self.assertRaises(AppError): login(self.db, "misaka", "wrong", 100)
        expired, _ = login(self.db, "misaka", "secret123", -1)
        self.assertIsNone(current_user(self.db, expired))
        with self.assertRaises(AppError): create_admin(self.db, "other", "密码密码12")


if __name__ == "__main__":
    unittest.main()
