"""
lllm.logging — logging and session persistence for LLLM.

Public API:
    LogBackend          — abstract KV storage driver
    LocalFileBackend    — one file per key under a root directory
    SQLiteBackend       — single SQLite file
    NoOpBackend         — silently discards everything
    LogStore            — persists / queries TacticCallSessions
    SessionRecord       — full session + metadata (returned by load_session_record)
    SessionSummary      — lightweight descriptor (returned by list_sessions)
    ColoredFormatter    — ANSI-colored logging.Formatter
    setup_logging       — convenience function to configure the lllm logger

Convenience factories:
    local_store(path, namespace)   — LocalFileBackend-backed LogStore
    sqlite_store(path, namespace)  — SQLiteBackend-backed LogStore
    noop_store(namespace)          — NoOpBackend-backed LogStore (dry run)
"""

from lllm.logging.backend import (
    LogBackend,
    LocalFileBackend,
    SQLiteBackend,
    NoOpBackend,
)
from lllm.logging.store import LogStore
from lllm.logging.models import SessionRecord, SessionSummary
from lllm.logging.formatter import ColoredFormatter, setup_logging


def local_store(
    path: str,
    namespace: str = "default",
    runtime=None,
) -> LogStore:
    """Create a LogStore backed by the local filesystem.

    Args:
        path:      Directory where session files will be written.
                   Created automatically if it does not exist.
        namespace: Logical prefix for all keys.  Separate stores can share
                   the same directory by using different namespaces.
        runtime:   Optional Runtime instance.  Enables alias resolution in
                   ``list_sessions(tactic_path=...)``.

    Example::

        store = local_store("~/.lllm/logs")
        store = local_store("/data/runs", namespace="exp-42", runtime=rt)
    """
    import os
    return LogStore(
        LocalFileBackend(os.path.expanduser(path)),
        namespace=namespace,
        runtime=runtime,
    )


def sqlite_store(
    path: str,
    namespace: str = "default",
    runtime=None,
) -> LogStore:
    """Create a LogStore backed by a single SQLite file.

    Preferred over ``local_store`` when you need atomic writes, concurrent
    access from multiple processes, or portability of the whole log as one file.

    Args:
        path:      Path to the ``.db`` file.  Parent directory is created
                   automatically.  Use ``:memory:`` for in-process testing.
        namespace: Logical prefix for all keys.
        runtime:   Optional Runtime instance for alias resolution.

    Example::

        store = sqlite_store("~/.lllm/logs.db")
        store = sqlite_store(":memory:", namespace="test")
    """
    import os
    return LogStore(
        SQLiteBackend(os.path.expanduser(path)),
        namespace=namespace,
        runtime=runtime,
    )


def noop_store(namespace: str = "default", runtime=None) -> LogStore:
    """Create a LogStore that silently discards everything.

    Useful for disabling persistence in tests or dry-run scripts without
    changing tactic code.

    Example::

        store = noop_store()
        tactic = build_tactic(config, ckpt_dir, log_store=store)
    """
    return LogStore(NoOpBackend(), namespace=namespace, runtime=runtime)


__all__ = [
    # Core abstractions
    "LogBackend",
    "LocalFileBackend",
    "SQLiteBackend",
    "NoOpBackend",
    "LogStore",
    # Data models
    "SessionRecord",
    "SessionSummary",
    # Terminal logging
    "ColoredFormatter",
    "setup_logging",
    # Convenience factories
    "local_store",
    "sqlite_store",
    "noop_store",
]
