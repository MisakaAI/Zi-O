from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .connection import connect

MIGRATION_RE = re.compile(r"^(?P<version>\d{4})_[^/]+\.sql$")


def migration_files(root: Path) -> list[tuple[int, Path]]:
    files: list[tuple[int, Path]] = []
    for path in sorted(root.glob("*.sql")):
        match = MIGRATION_RE.match(path.name)
        if match:
            files.append((int(match.group("version")), path))
    return files


def migrate(database_path: Path, migrations_root: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    files = migration_files(migrations_root)
    with connect(database_path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at INTEGER NOT NULL)")
        current = db.execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_version").fetchone()["version"]
        for version, path in files:
            if version <= current:
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                # executescript commits any pending transaction before running;
                # put the migration and its ledger row in one explicit script transaction.
                db.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + sql
                    + "\nINSERT INTO schema_version(version, name, applied_at) VALUES ("
                    + str(version)
                    + ", "
                    + repr(path.name)
                    + ", CAST(strftime('%s','now') AS INTEGER) * 1000);\nCOMMIT;"
                )
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
            current = version
