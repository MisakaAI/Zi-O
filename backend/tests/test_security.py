"""安全边界回归测试,覆盖签名游标与文件路径逃逸防护."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.api.public import _cursor_scope
from app.errors import AppError
from app.files import resolve_static, resolve_upload
from app.security import make_cursor, read_cursor


class SecurityTests(unittest.TestCase):
    """验证后端不透明游标和受管理文件路径的安全约束."""

    def test_cursor_is_signed_and_scope_payload_is_preserved(self):
        """验证游标签名不可篡改,并能保留查询作用域载荷."""
        token = make_cursor({"v": 1, "scope": {"tag": "x"}, "started_at": 1, "id": 2}, b"secret")
        self.assertEqual(read_cursor(token, b"secret")["id"], 2)
        with self.assertRaises(ValueError):
            read_cursor(token[:-1] + ("a" if token[-1] != "a" else "b"), b"secret")
        with self.assertRaises(AppError) as caught:
            _cursor_scope("not-a-cursor", {"tag": "x"}, b"secret")
        self.assertEqual(caught.exception.code, "cursor_invalid")

    def test_static_path_rejects_traversal_symlink_and_non_html(self):
        """验证静态页拒绝穿越,规范化绕过,符号链接和非 HTML 文件."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "pages"
            root.mkdir()
            (root / "ok.html").write_text("<h1>ok</h1>")
            outside = Path(tmp) / "outside.html"
            outside.write_text("secret")
            (root / "link.html").symlink_to(outside)
            self.assertEqual(resolve_static(root, "ok.html", 1024).name, "ok.html")
            for path in ("../outside.html", "foo/../ok.html", "foo/./ok.html", "/tmp/out.html", "link.html", "ok.txt", "missing.html"):
                with self.assertRaises(AppError):
                    resolve_static(root, path, 1024)

    def test_upload_path_rejects_traversal_and_symlink(self):
        """验证上传文件解析拒绝穿越,绝对路径,符号链接和不存在文件."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "uploads"
            root.mkdir()
            (root / "ok.png").write_bytes(b"png")
            outside = Path(tmp) / "outside.png"
            outside.write_bytes(b"secret")
            (root / "link.png").symlink_to(outside)

            self.assertEqual(resolve_upload(root, "ok.png").name, "ok.png")
            for path in ("../outside.png", "/tmp/out.png", "link.png", "missing.png"):
                with self.assertRaises(AppError):
                    resolve_upload(root, path)
