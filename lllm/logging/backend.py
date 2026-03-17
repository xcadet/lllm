"""
LogBackend — raw key-value storage drivers for LogStore.

All backends implement four abstract methods:
    put(key, data)     — write bytes under a string key
    get(key)           — read bytes for a key, or None if missing
    list_keys(prefix)  — enumerate all keys with the given prefix
    delete(key)        — remove a key

Keys are forward-slash-separated strings (e.g. "ns/sessions/abc123").
"""
from __future__ import annotations

import os
import sqlite3
from abc import ABC, abstractmethod
from typing import List, Optional


class LogBackend(ABC):
    """Raw key-value storage. Keys are strings, values are bytes."""

    @abstractmethod
    def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def get(self, key: str) -> Optional[bytes]: ...

    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalFileBackend(LogBackend):
    """
    Stores each key as a file under root_dir.

    Key "ns/sessions/abc123" → file "{root_dir}/ns/sessions/abc123"
    """

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        os.makedirs(root_dir, exist_ok=True)

    def _key_to_path(self, key: str) -> str:
        # Normalise forward slashes to OS separator
        rel = os.path.join(*key.split("/"))
        return os.path.join(self.root_dir, rel)

    def put(self, key: str, data: bytes) -> None:
        path = self._key_to_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def get(self, key: str) -> Optional[bytes]:
        path = self._key_to_path(key)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def list_keys(self, prefix: str = "") -> List[str]:
        prefix_path = self._key_to_path(prefix) if prefix else self.root_dir
        keys: List[str] = []
        if not os.path.exists(prefix_path):
            return keys
        if os.path.isfile(prefix_path):
            return [prefix]
        for dirpath, _, filenames in os.walk(prefix_path):
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                rel = os.path.relpath(abs_path, self.root_dir)
                key = rel.replace(os.sep, "/")
                keys.append(key)
        return keys

    def delete(self, key: str) -> None:
        path = self._key_to_path(key)
        if os.path.exists(path):
            os.remove(path)


class SQLiteBackend(LogBackend):
    """
    Stores all key-value pairs in a single SQLite file.

    Useful for atomic writes and avoiding filesystem limitations.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS kv "
                "(key TEXT PRIMARY KEY, data BLOB NOT NULL)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_key ON kv(key)")

    def put(self, key: str, data: bytes) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO kv (key, data) VALUES (?, ?)",
                (key, data),
            )

    def get(self, key: str) -> Optional[bytes]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM kv WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else None

    def list_keys(self, prefix: str = "") -> List[str]:
        with self._connect() as conn:
            if prefix:
                rows = conn.execute(
                    "SELECT key FROM kv WHERE key LIKE ?",
                    (prefix.rstrip("/") + "%",),
                ).fetchall()
            else:
                rows = conn.execute("SELECT key FROM kv").fetchall()
        return [row[0] for row in rows]

    def delete(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM kv WHERE key = ?", (key,))


class NoOpBackend(LogBackend):
    """Silently discards all writes. For when the user opts out of logging."""

    def put(self, key: str, data: bytes) -> None:
        pass

    def get(self, key: str) -> Optional[bytes]:
        return None

    def list_keys(self, prefix: str = "") -> List[str]:
        return []

    def delete(self, key: str) -> None:
        pass
