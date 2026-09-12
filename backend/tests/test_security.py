from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.errors import AppError
from app.api.public import _cursor_scope
from app.files import resolve_static
from app.security import make_cursor, read_cursor


class SecurityTests(unittest.TestCase):
    def test_cursor_is_signed_and_scope_payload_is_preserved(self):
        token = make_cursor({"v": 1, "scope": {"tag": "x"}, "started_at": 1, "id": 2}, b"secret")
        self.assertEqual(read_cursor(token, b"secret")["id"], 2)
        with self.assertRaises(ValueError):
            read_cursor(token[:-1] + ("a" if token[-1] != "a" else "b"), b"secret")
        with self.assertRaises(AppError) as caught:
            _cursor_scope("not-a-cursor", {"tag": "x"}, b"secret")
        self.assertEqual(caught.exception.code, "cursor_invalid")

    def test_static_path_rejects_traversal_symlink_and_non_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "pages"; root.mkdir(); (root / "ok.html").write_text("<h1>ok</h1>")
            outside = Path(tmp) / "outside.html"; outside.write_text("secret")
            (root / "link.html").symlink_to(outside)
            self.assertEqual(resolve_static(root, "ok.html", 1024).name, "ok.html")
            for path in ("../outside.html", "foo/../ok.html", "foo/./ok.html", "/tmp/out.html", "link.html", "ok.txt", "missing.html"):
                with self.assertRaises(AppError): resolve_static(root, path, 1024)
