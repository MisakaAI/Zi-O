from __future__ import annotations

import sqlite3
from contextlib import suppress

from ..errors import AppError
from ..repositories.content import purge_sessions, user_by_session, user_by_username
from ..security import hash_password, new_session_token, token_hash, validate_password, verify_password
from ..timeutil import now_ms

COOKIE_NAME = "zio_session"


def public_user(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "username": row["username"], "nickname": row["nickname"], "display_name": row["nickname"] or row["username"]}


def create_admin(db: sqlite3.Connection, username: str, password: str, nickname: str = "") -> dict:
    username = username.strip()
    if not username or len(username) > 64:
        raise AppError("invalid_username", "username is invalid", 422)
    error = validate_password(password)
    if error:
        raise AppError(error, "password must be at least 6 characters and contain letters and numbers", 422)
    if user_by_username(db, username):
        raise AppError("user_exists", "administrator already exists", 409)
    digest, salt, iterations = hash_password(password)
    stamp = now_ms()
    db.execute(
        "INSERT INTO users(username,nickname,password_hash,password_salt,password_iterations,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (username, nickname[:120], digest, salt, iterations, stamp, stamp),
    )
    return public_user(user_by_username(db, username))


def login(db: sqlite3.Connection, username: str, password: str, ttl_seconds: int) -> tuple[str, dict]:
    row = user_by_username(db, username.strip())
    if row is None or not verify_password(password, row["password_hash"], row["password_salt"], row["password_iterations"]):
        raise AppError("invalid_credentials", "username or password is incorrect", 401)
    if row["password_iterations"] < 600_000:
        digest, salt, iterations = hash_password(password)
        db.execute("UPDATE users SET password_hash=?,password_salt=?,password_iterations=?,updated_at=? WHERE id=?", (digest, salt, iterations, now_ms(), row["id"]))
    token, digest = new_session_token()
    stamp = now_ms()
    purge_sessions(db, stamp)
    db.execute("INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)", (digest, row["id"], stamp + ttl_seconds * 1000, stamp))
    return token, public_user(row)


def current_user(db: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    try:
        digest = token_hash(token)
    except (UnicodeEncodeError, ValueError):
        return None
    return user_by_session(db, digest, now_ms())


def logout(db: sqlite3.Connection, token: str | None) -> None:
    if token:
        with suppress(UnicodeEncodeError, ValueError):
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))
