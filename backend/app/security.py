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
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return digest, salt, iterations


def verify_password(password: str, digest: bytes, salt: bytes, iterations: int) -> bool:
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, digest)


def validate_password(password: str) -> str | None:
    if len(password) < 6 or len(password) > 256:
        return "password_length"
    if not any("a" <= ch.lower() <= "z" for ch in password) or not any("0" <= ch <= "9" for ch in password):
        return "password_complexity"
    return None


def new_session_token() -> tuple[str, bytes]:
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    return token, hashlib.sha256(token.encode("ascii")).digest()


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii")).digest()


def make_cursor(payload: dict, secret: bytes) -> str:
    import json

    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret, raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + signature).decode("ascii").rstrip("=")


def read_cursor(value: str, secret: bytes) -> dict:
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
    id: int
    username: str
    nickname: str


def same_origin(request: Request, settings: Settings) -> bool:
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/") == settings.public_origin
    referer = request.headers.get("referer")
    return bool(referer and referer.startswith(settings.public_origin + "/"))
