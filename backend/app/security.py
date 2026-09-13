"""密码,会话,签名游标和请求来源校验等安全原语."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from fastapi import Request

from .config import Settings

PBKDF2_ITERATIONS = 600_000
SESSION_TOKEN_BYTES = 32


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> tuple[bytes, bytes, int]:
    """为密码生成随机盐和 PBKDF2-SHA256 摘要,并返回所用参数."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return digest, salt, iterations


def verify_password(password: str, digest: bytes, salt: bytes, iterations: int) -> bool:
    """使用保存的盐和迭代次数验证密码,比较时采用常量时间比较."""
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, digest)


def validate_password(password: str) -> str | None:
    """检查密码长度及字母,数字复杂度,返回稳定错误码或 None."""
    if len(password) < 6 or len(password) > 256:
        return "password_length"
    if not any("a" <= ch.lower() <= "z" for ch in password) or not any("0" <= ch <= "9" for ch in password):
        return "password_complexity"
    return None


def new_session_token() -> tuple[str, bytes]:
    """生成不透明会话令牌,并返回令牌及其应存入数据库的 SHA-256 摘要."""
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    return token, hashlib.sha256(token.encode("ascii")).digest()


def token_hash(token: str) -> bytes:
    """把 Cookie 中的会话令牌转换为数据库查询使用的哈希值."""
    return hashlib.sha256(token.encode("ascii")).digest()


def make_cursor(payload: dict, secret: bytes) -> str:
    """对分页游标载荷签名并编码,防止客户端篡改排序位置或查询范围."""
    import json

    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret, raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + signature).decode("ascii").rstrip("=")


def read_cursor(value: str, secret: bytes) -> dict:
    """验证并解码签名游标;任何格式,签名或版本错误都统一抛出 ValueError."""
    import json

    if len(value) > 2048:
        raise ValueError("cursor_too_long")
    try:
        padded = value + "=" * (-len(value) % 4)
        data = base64.urlsafe_b64decode(padded.encode("ascii"))
        if len(data) <= hashlib.sha256().digest_size:
            raise ValueError("cursor_invalid")
        raw, signature = data[:-hashlib.sha256().digest_size], data[-hashlib.sha256().digest_size:]
        expected = hmac.new(secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("cursor_invalid")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise ValueError("cursor_invalid")
        return payload
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cursor_invalid") from exc


@dataclass(frozen=True)
class AuthUser:
    """从数据库映射出的最小管理员身份信息."""

    id: int
    username: str
    nickname: str


def same_origin(request: Request, settings: Settings) -> bool:
    """校验写请求的 Origin 或 Referer 是否来自配置的站点来源."""
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/") == settings.public_origin
    referer = request.headers.get("referer")
    return bool(referer and referer.startswith(settings.public_origin + "/"))
