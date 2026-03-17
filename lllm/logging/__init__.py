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

__all__ = [
    "LogBackend",
    "LocalFileBackend",
    "SQLiteBackend",
    "NoOpBackend",
    "LogStore",
    "SessionRecord",
    "SessionSummary",
    "ColoredFormatter",
    "setup_logging",
]
