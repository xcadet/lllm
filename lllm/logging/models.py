"""
Data models for LogStore results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SessionRecord:
    """Full session data + metadata as returned by LogStore.load_session_record()."""

    session_id: str
    session: Any  # TacticCallSession — typed as Any to avoid circular import
    tags: Dict[str, str]
    metadata: Dict[str, Any]
    timestamp: str          # ISO-8601
    traceback: Optional[str]  # full traceback string if session failed


@dataclass
class SessionSummary:
    """Lightweight session descriptor returned by LogStore.list_sessions()."""

    session_id: str
    tactic_name: str
    tactic_path: str        # stable ID: "{package_name}::{tactic_name}", e.g. "my_pkg::researcher"
    state: str
    total_cost: float
    agent_call_count: int
    timestamp: str          # ISO-8601
    tags: Dict[str, str] = field(default_factory=dict)
