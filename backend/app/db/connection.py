from __future__ import annotations

import sqlite3
from pathlib import Path


class Connection(sqlite3.Connection):
    """Connection that also closes when used as a context manager."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(path: Path | str) -> sqlite3.Connection:
    # FastAPI may resolve a synchronous dependency in its worker thread and
    # execute an async endpoint on the event-loop thread. Each request owns
    # this connection, so allowing that hand-off is safe and avoids leaking
    # a connection across requests.
    connection = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False, factory=Connection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection
