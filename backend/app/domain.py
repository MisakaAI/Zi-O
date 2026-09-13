"""领域层的输入规范化,路径校验,slug 和 Item 元数据规则."""

from __future__ import annotations

import json
import unicodedata
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import AppError

METADATA_KEYS: dict[str, dict[str, type | tuple[type, ...]]] = {
    "JOURNAL": {"location": str},
    "BOOK": {"isbn": str, "publisher": str, "published_year": int, "page_count": int},
    "MOVIE": {"release_year": int, "runtime_minutes": int, "country": str},
    "GAME": {"release_year": int, "platform": str, "play_status": str},
    "PROJECT": {"repository_url": str, "language": str, "project_status": str},
}


def normalize_text(value: str, max_length: int, field: str, *, allow_empty: bool = True) -> str:
    """去除首尾空白并执行字段的空值与长度限制."""
    value = value.strip()
    if not allow_empty and not value:
        raise AppError("invalid_input", f"{field} cannot be empty", 422)
    if len(value) > max_length:
        raise AppError("input_too_long", f"{field} exceeds its length limit", 422)
    return value


def validate_static_path(value: str | None) -> str | None:
    """校验静态页路径必须是根目录内的规范相对 HTML 路径."""
    if value is None or value == "":
        return None
    if "\x00" in value or "\\" in value or value.startswith("/"):
        raise AppError("invalid_static_path", "static_path must be a relative HTML path", 422)
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise AppError("invalid_static_path", "static_path must be a relative .html path", 422)
    path = PurePosixPath(value)
    if path.suffix.lower() != ".html":
        raise AppError("invalid_static_path", "static_path must be a relative .html path", 422)
    if len(value) > 512:
        raise AppError("input_too_long", "static_path exceeds its length limit", 422)
    return value


def slugify(value: str) -> str:
    """把显示名称转换为稳定,适合 URL 的小写 slug."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    pieces: list[str] = []
    for char in normalized:
        if char.isalnum():
            pieces.append(char)
        elif pieces and pieces[-1] != "-":
            pieces.append("-")
    slug = "".join(pieces).strip("-")
    return slug or "tag"


def name_key(value: str) -> str:
    """生成用于大小写和 Unicode 规范化去重的名称键."""
    return unicodedata.normalize("NFKC", value).casefold().strip()


def validate_metadata(root_code: str, value: dict) -> str:
    """按 Item 根分类校验元数据字段,类型,范围和序列化大小."""
    if not isinstance(value, dict) or len(value) > 20:
        raise AppError("invalid_metadata", "metadata_json must be a small object", 422)
    allowed = METADATA_KEYS.get(root_code, {})
    for key, item in value.items():
        if key not in allowed or not isinstance(key, str) or len(key) > 64:
            raise AppError("invalid_metadata", f"metadata key is not allowed for {root_code}", 422)
        expected = allowed[key]
        if not isinstance(item, expected) or isinstance(item, bool):
            raise AppError("invalid_metadata", f"metadata.{key} has an invalid type", 422)
        if isinstance(item, str) and len(item) > 2048:
            raise AppError("input_too_long", f"metadata.{key} is too long", 422)
        if isinstance(item, int) and not 0 <= item <= 10_000_000:
            raise AppError("invalid_metadata", f"metadata.{key} is out of range", 422)
        if key == "repository_url" and not item.startswith(("https://", "http://")):
            raise AppError("invalid_metadata", "repository_url must use http or https", 422)
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > 16_384:
        raise AppError("input_too_large", "metadata_json is too large", 422)
    return encoded


def validate_timezone(value: str) -> str:
    """确认时区名称可由系统的 IANA 时区数据库解析."""
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise AppError("invalid_timezone", "timezone is not recognized", 422) from exc
    return value
