"""创建带有 SQLite 运行约束的数据库连接."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class Connection(sqlite3.Connection):
    """支持上下文管理器退出时自动关闭的 SQLite 连接."""

    def __exit__(self, exc_type, exc_value, traceback):
        """先交给 SQLite 提交或回滚,再无条件释放连接资源."""
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(path: Path | str) -> sqlite3.Connection:
    """打开一个启用外键,WAL 和忙等待的按请求 SQLite 连接."""
    # FastAPI 可能在线程池解析同步依赖,再在事件循环线程执行异步端点.
    # 连接只归当前请求所有,因此允许线程切换可以避免跨请求共享或泄漏连接.
    connection = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False, factory=Connection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection
