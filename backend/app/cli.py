"""ZI/O 命令行入口,提供迁移,首次建管理员和在线备份命令."""

from __future__ import annotations

import argparse
import getpass
import sqlite3
from pathlib import Path

from .config import Settings
from .db.connection import connect
from .db.migrations import migrate
from .errors import AppError
from .services.auth import create_admin


def parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器及其三个子命令."""
    result = argparse.ArgumentParser(prog="zio")
    sub = result.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-admin", help="create the first administrator")
    init.add_argument("--username", default="misaka")
    init.add_argument("--nickname", default="")
    backup = sub.add_parser("backup", help="make an online SQLite backup")
    backup.add_argument("output", type=Path)
    sub.add_parser("migrate", help="apply pending migrations")
    return result


def main() -> int:
    """解析命令并执行迁移,管理员初始化或 SQLite 在线备份."""
    args = parser().parse_args()
    settings = Settings.from_env()
    settings.ensure_directories()
    migrate(settings.database_path, Path(__file__).parents[1] / "migrations")
    if args.command == "migrate":
        print("migrations applied")
        return 0
    if args.command == "init-admin":
        first = getpass.getpass("Initial administrator password: ")
        second = getpass.getpass("Repeat password: ")
        if first != second:
            print("passwords do not match")
            return 2
        with connect(settings.database_path) as db:
            try:
                user = create_admin(db, args.username, first, args.nickname)
            except AppError as exc:
                print(exc.message)
                return 2
        print(f"created administrator {user['username']}")
        return 0
    if args.command == "backup":
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        # 使用 SQLite backup API 读取一致性快照,避免直接复制正在写入的数据库文件.
        source = sqlite3.connect(settings.database_path)
        destination = sqlite3.connect(output)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        print(f"backup written to {output}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
