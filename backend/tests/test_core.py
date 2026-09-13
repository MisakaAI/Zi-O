from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.api.manage import notes as manage_notes
from app.api.manage import upload_content_image
from app.api.public import tag as public_tag
from app.db.connection import connect
from app.db.migrations import migrate
from app.errors import AppError
from app.rendering import render_content
from app.repositories import content as repo
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
        self.db.close()
        self.temp.cleanup()

    def note(self, **overrides):
        values = {"started_at": "2024-01-01T00:00:00Z", "visibility": "private", "title": "event"}
        values.update(overrides)
        return content.create_note(self.db, NoteWrite(**values))

    def test_migration_and_archive_numbers(self):
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM categories WHERE is_root=1").fetchone()[0], 5)
        note_columns = {row["name"] for row in self.db.execute("PRAGMA table_info(notes)")}
        self.assertNotIn("content_format", note_columns)
        project = self.db.execute("SELECT id, name FROM categories WHERE code='PROJECT'").fetchone()
        self.assertEqual(project["name"], "Project")
        item = content.create_item(
            self.db,
            ItemWrite(category_id=project["id"], title="ZI/O", metadata_json={"repository_url": "https://example.com/zio"}),
        )
        self.assertEqual(item["category_code"], "PROJECT")
        first = self.note()
        second = self.note(started_at="2020-01-01T00:00:00Z")
        self.assertEqual((first["archive_no"], second["archive_no"]), (1, 2))
        self.db.execute("DELETE FROM notes WHERE id=?", (first["id"],))
        third = self.note()
        self.assertEqual(third["archive_no"], 3)
        migrate(self.root / "test.sqlite3", Path(__file__).parents[1] / "migrations")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0], 3)
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

    def test_public_calendar_uses_site_timezone_and_filters_private_notes(self):
        self.note(title="late January", started_at="2024-01-31T16:30:00Z", visibility="public")
        self.note(title="February", started_at="2024-02-01T08:00:00Z", visibility="public")
        self.note(title="private", started_at="2024-02-01T09:00:00Z", visibility="private")
        private_item = content.create_item(self.db, ItemWrite(category_id=2, title="Hidden", visibility="private"))
        hidden_link = self.note(title="hidden item", started_at="2024-02-01T10:00:00Z", visibility="public")
        self.db.execute("INSERT INTO note_items(note_id,item_id) VALUES(?,?)", (hidden_link["id"], private_item["id"]))
        days = content.public_calendar(self.db, 2024, 2, "Asia/Shanghai")
        self.assertEqual(days, [{"date": "2024-02-01", "count": 2}])

    def test_public_note_rejects_private_item_link(self):
        private_item = content.create_item(self.db, ItemWrite(category_id=2, title="Hidden", visibility="private"))
        with self.assertRaises(AppError) as caught:
            self.note(visibility="public", items=[ItemLink(item_id=private_item["id"])])
        self.assertEqual(caught.exception.code, "private_item_link")

    def test_rendering_removes_xss(self):
        html = render_content('<script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:bad()">x</a>')
        self.assertNotIn("script", html.lower())
        self.assertNotIn("onerror", html.lower())
        self.assertNotIn("javascript:", html.lower())

    def test_note_content_is_unified_sanitized_html(self):
        note = self.note(content_raw="<h2>Rich text</h2><p><strong>safe</strong><iframe src='https://example.com'></iframe></p>")
        self.assertEqual(note["content_raw"], "<h2>Rich text</h2><p><strong>safe</strong><iframe src='https://example.com'></iframe></p>")
        self.assertNotIn("content_format", note)
        self.assertIn("<strong>safe</strong>", note["content_html_sanitized"])
        self.assertNotIn("iframe", note["content_html_sanitized"])

    def test_tag_slug_conflict(self):
        first = content.create_tag(self.db, TagWrite(name="Read later"))
        second = content.create_tag(self.db, TagWrite(name="Read-later"))
        self.assertEqual(first["slug"], "read-later")
        self.assertEqual(second["slug"], "read-later-2")

    def test_note_body_hashtags_create_and_sync_tags(self):
        existing = content.create_tag(self.db, TagWrite(name="Python"))
        note = self.note(content_raw="<p>今天 <strong>#python</strong> 和 #读书。</p><pre>#code</pre><p>#读书 #new_tag</p>")

        self.assertEqual({tag["name"] for tag in note["tags"]}, {"Python", "读书", "new_tag"})
        self.assertIn(existing["id"], {tag["id"] for tag in note["tags"]})

        updated = content.update_note(self.db, note["id"], NotePatch(content_raw="<p>只保留 #读书</p>"))
        self.assertEqual([tag["name"] for tag in updated["tags"]], ["读书"])

    def test_note_body_hashtags_render_as_safe_links(self):
        note = self.note(content_raw='<p>#读书 <code>#code</code></p><img src="/api/content-images/deadbeef" onerror="x">')

        self.assertIn('class="hashtag-link" href="/tag/', note["content_html_sanitized"])
        self.assertIn("<code>#code</code>", note["content_html_sanitized"])
        self.assertNotIn("onerror", note["content_html_sanitized"])

    def test_content_images_follow_note_visibility_and_sync(self):
        image_id = "a" * 32
        self.db.execute(
            "INSERT INTO content_images(id,storage_path,media_type,created_at) VALUES(?,?,?,?)",
            (image_id, f"{image_id}.png", "image/png", 1),
        )
        note = self.note(content_raw=f'<p>image</p><img src="/api/content-images/{image_id}" alt="sample">')

        self.assertIsNone(repo.get_content_image(self.db, image_id, public=True))
        content.update_note(self.db, note["id"], NotePatch(visibility="public"))
        public_image = repo.get_content_image(self.db, image_id, public=True)
        self.assertEqual(public_image["id"], image_id)
        private_item = content.create_item(self.db, ItemWrite(category_id=2, title="Hidden", visibility="private"))
        self.db.execute("INSERT INTO note_items(note_id,item_id) VALUES(?,?)", (note["id"], private_item["id"]))
        self.assertIsNone(repo.get_content_image(self.db, image_id, public=True))
        self.db.execute("DELETE FROM note_items WHERE note_id=? AND item_id=?", (note["id"], private_item["id"]))
        content.update_note(self.db, note["id"], NotePatch(content_raw="<p>removed</p>"))
        self.assertIsNone(repo.get_content_image(self.db, image_id, public=True))

        missing_image_id = "b" * 32
        with self.assertRaises(AppError) as caught:
            self.note(content_raw=f'<img src="/api/content-images/{missing_image_id}">')
        self.assertEqual(caught.exception.code, "image_not_found")

    def test_multiple_tag_filter_requires_all_selected_tags(self):
        self.note(title="both", visibility="public", content_raw="<p>#one #two</p>")
        self.note(title="one", visibility="public", content_raw="<p>#one</p>")
        rows = __import__("app.repositories.content", fromlist=["timeline_rows"]).timeline_rows(
            self.db, public=True, limit=20, tag_slugs=["one", "two"]
        )

        self.assertEqual([row["title"] for row in rows], ["both"])

        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(secret_key=b"test-secret")))
        )
        response = public_tag(slug="one", request=request, tag=["two"], cursor=None, limit=20, db=self.db)
        self.assertEqual([item["title"] for item in response["items"]], ["both"])
        self.assertEqual([tag["slug"] for tag in response["tags"]], ["one", "two"])

    def test_content_image_upload_writes_random_managed_file(self):
        body = b"\x89PNG\r\n\x1a\ncontent"
        self_root = self.root

        class Request:
            def __init__(self):
                self.headers = {"content-type": "image/png"}
                self.app = SimpleNamespace(
                    state=SimpleNamespace(
                        settings=SimpleNamespace(
                            uploads_root=self_root / "uploads", max_content_image_bytes=5 * 1024 * 1024
                        )
                    )
                )

            async def stream(self):
                yield body

        result = asyncio.run(upload_content_image(request=Request(), db=self.db))

        self.assertEqual(result["media_type"], "image/png")
        self.assertEqual(len(result["id"]), 32)
        self.assertEqual((self.root / "uploads" / f'{result["id"]}.png').read_bytes(), body)

    def test_private_only_tag_is_not_in_public_index(self):
        tag = content.create_tag(self.db, TagWrite(name="Secret tag"))
        self.note(tag_ids=[tag["id"]], visibility="private")
        rows = __import__("app.repositories.content", fromlist=["public_tags"]).public_tags(self.db)
        self.assertEqual(rows, [])

    def test_password_and_session(self):
        create_admin(self.db, "misaka", "secret123")
        token, user = login(self.db, "misaka", "secret123", 100)
        self.assertTrue(token)
        self.assertEqual(user["username"], "misaka")
        with self.assertRaises(AppError):
            login(self.db, "misaka", "wrong", 100)
        expired, _ = login(self.db, "misaka", "secret123", -1)
        self.assertIsNone(current_user(self.db, expired))
        with self.assertRaises(AppError):
            create_admin(self.db, "other", "密码密码12")


if __name__ == "__main__":
    unittest.main()
