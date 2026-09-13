"""发现并按版本顺序执行数据库迁移."""

from __future__ import annotations

import re
from pathlib import Path

from .connection import connect

MIGRATION_RE = re.compile(r"^(?P<version>\d{4})_[^/]+\.sql$")


def migration_files(root: Path) -> list[tuple[int, Path]]:
    """返回符合四位版本命名约定的迁移文件,并按文件名排序."""
    files: list[tuple[int, Path]] = []
    for path in sorted(root.glob("*.sql")):
        match = MIGRATION_RE.match(path.name)
        if match:
            files.append((int(match.group("version")), path))
    return files


def migrate(database_path: Path, migrations_root: Path) -> None:
    """把尚未登记的迁移应用到数据库,并写入版本账本."""
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
                # executescript 会先提交挂起事务,因此显式把迁移和账本记录包在同一事务中.
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
