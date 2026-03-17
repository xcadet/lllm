"""
LogStore — the public API for persisting and querying TacticCallSessions.

Sits on top of a LogBackend (raw KV storage) and handles:
    - Serialisation / deserialisation
    - Session ID generation
    - Timestamp tracking
    - Tag-based indexing and filtering
    - Full traceback capture for failed sessions
    - Cost aggregation
    - Export helpers
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import traceback as tb
import uuid
from typing import Any, Dict, List, Optional

from lllm.logging.backend import LogBackend
from lllm.logging.models import SessionRecord, SessionSummary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _make_json_safe(obj: Any) -> Any:
    """Recursively convert non-JSON-serialisable values to strings."""
    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(item) for item in obj]
    if isinstance(obj, Exception):
        return f"{type(obj).__name__}: {obj}"
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def _serialize_session(session: Any) -> bytes:
    """Serialise a TacticCallSession to JSON bytes."""
    try:
        # Prefer Pydantic's own serialiser when available
        raw = json.loads(session.model_dump_json())
    except Exception:
        try:
            raw = session.model_dump()
        except Exception:
            raw = vars(session)
    safe = _make_json_safe(raw)
    return json.dumps(safe).encode()


def _deserialize_session(data: bytes) -> Any:
    """Deserialise a TacticCallSession from JSON bytes."""
    # Import here to avoid circular imports at module load time
    from lllm.core.tactic import TacticCallSession
    raw = json.loads(data.decode())
    return TacticCallSession.model_validate(raw)


# ---------------------------------------------------------------------------
# LogStore
# ---------------------------------------------------------------------------

class LogStore:
    """
    Persists and queries TacticCallSessions.

    This is the only public API that tactics and users interact with.
    LogBackend is the storage driver and is intentionally trivial to swap.

    Args:
        backend:   A LogBackend instance (LocalFileBackend, SQLiteBackend, etc.).
        namespace: Logical prefix for all keys.  Defaults to ``"default"``.
                   Typically set to the package/runtime name.
    """

    def __init__(self, backend: LogBackend, namespace: str = "default"):
        self._backend = backend
        self._ns = namespace.strip("/")

    # ------------------------------------------------------------------
    # Internal key helpers
    # ------------------------------------------------------------------

    def _session_key(self, session_id: str) -> str:
        return f"{self._ns}/sessions/{session_id}"

    def _index_key(self, session_id: str) -> str:
        return f"{self._ns}/index/{session_id}"

    def _error_key(self, error_id: str) -> str:
        return f"{self._ns}/errors/{error_id}"

    def _gen_id(self) -> str:
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:8]
        return f"{ts}_{uid}"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_session(
        self,
        session: Any,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Persist a TacticCallSession.

        Returns the generated ``session_id``.

        What gets saved:
        - Full serialised session (model_dump_json)
        - tags dict (for filtering in list_sessions)
        - metadata dict (arbitrary user data)
        - ISO timestamp
        - Full traceback string when session.state == "failure"
        """
        session_id = self._gen_id()
        timestamp = dt.datetime.now().isoformat()
        tags = dict(tags or {})
        metadata = dict(metadata or {})

        # Capture traceback for failed sessions
        traceback_str: Optional[str] = None
        if getattr(session, "state", None) == "failure":
            traceback_str = getattr(session, "error_traceback", None)

        # Build index entry (lightweight — no full session data)
        try:
            total_cost = float(session.total_cost.cost)
        except Exception:
            total_cost = 0.0
        try:
            agent_call_count = int(session.agent_call_count)
        except Exception:
            agent_call_count = 0

        index_entry = {
            "session_id": session_id,
            "tactic_name": getattr(session, "tactic_name", "unknown"),
            "state": getattr(session, "state", "unknown"),
            "total_cost": total_cost,
            "agent_call_count": agent_call_count,
            "timestamp": timestamp,
            "tags": tags,
            "metadata": metadata,
            "traceback": traceback_str,
        }

        try:
            session_bytes = _serialize_session(session)
            self._backend.put(self._session_key(session_id), session_bytes)
            self._backend.put(
                self._index_key(session_id),
                json.dumps(index_entry).encode(),
            )
        except Exception as e:
            logger.error("LogStore failed to save session %s: %s", session_id, e, exc_info=True)
            raise

        logger.debug(
            "Session saved — id=%s tactic=%s state=%s cost=%.6f",
            session_id,
            index_entry["tactic_name"],
            index_entry["state"],
            total_cost,
        )
        return session_id

    def save_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Persist a standalone error (outside of a tactic session).

        Captures type, message, and full traceback.
        Returns the generated error_id.
        """
        error_id = self._gen_id()
        payload = {
            "error_id": error_id,
            "timestamp": dt.datetime.now().isoformat(),
            "type": type(error).__name__,
            "message": str(error),
            "traceback": tb.format_exc(),
            "context": _make_json_safe(context or {}),
        }
        self._backend.put(self._error_key(error_id), json.dumps(payload).encode())
        return error_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load_session(self, session_id: str) -> Any:
        """Deserialise and return the full TacticCallSession object."""
        data = self._backend.get(self._session_key(session_id))
        if data is None:
            raise KeyError(f"Session '{session_id}' not found in LogStore (namespace={self._ns!r})")
        return _deserialize_session(data)

    def load_session_record(self, session_id: str) -> SessionRecord:
        """Return session + tags + metadata + timestamp as a SessionRecord."""
        session = self.load_session(session_id)
        index_data = self._backend.get(self._index_key(session_id))
        if index_data is None:
            return SessionRecord(
                session_id=session_id,
                session=session,
                tags={},
                metadata={},
                timestamp="",
                traceback=None,
            )
        index = json.loads(index_data.decode())
        return SessionRecord(
            session_id=session_id,
            session=session,
            tags=index.get("tags", {}),
            metadata=index.get("metadata", {}),
            timestamp=index.get("timestamp", ""),
            traceback=index.get("traceback"),
        )

    def list_sessions(
        self,
        tags: Optional[Dict[str, str]] = None,
        after: Optional[dt.datetime] = None,
        before: Optional[dt.datetime] = None,
        tactic_name: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> List[SessionSummary]:
        """
        Query sessions by tags, time range, tactic name, or state.

        Returns lightweight summaries without loading full session data.
        Results are sorted newest-first.
        """
        prefix = f"{self._ns}/index/"
        all_keys = self._backend.list_keys(prefix)

        summaries: List[SessionSummary] = []
        for key in all_keys:
            if len(summaries) >= limit:
                break
            raw = self._backend.get(key)
            if raw is None:
                continue
            try:
                entry = json.loads(raw.decode())
            except Exception:
                continue

            # Apply filters
            if tags:
                entry_tags = entry.get("tags", {})
                if not all(entry_tags.get(k) == v for k, v in tags.items()):
                    continue

            entry_ts_str = entry.get("timestamp", "")
            if after or before:
                try:
                    entry_ts = dt.datetime.fromisoformat(entry_ts_str)
                    if after and entry_ts < after:
                        continue
                    if before and entry_ts > before:
                        continue
                except (ValueError, TypeError):
                    pass

            if tactic_name and entry.get("tactic_name") != tactic_name:
                continue

            if state and entry.get("state") != state:
                continue

            summaries.append(
                SessionSummary(
                    session_id=entry["session_id"],
                    tactic_name=entry.get("tactic_name", "unknown"),
                    state=entry.get("state", "unknown"),
                    total_cost=entry.get("total_cost", 0.0),
                    agent_call_count=entry.get("agent_call_count", 0),
                    timestamp=entry_ts_str,
                    tags=entry.get("tags", {}),
                )
            )

        summaries.sort(key=lambda s: s.timestamp, reverse=True)
        return summaries

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_session(self, session_id: str, format: str = "json") -> str:
        """Export a session as a JSON string (other formats reserved for future)."""
        data = self._backend.get(self._session_key(session_id))
        if data is None:
            raise KeyError(f"Session '{session_id}' not found")
        if format == "json":
            return json.dumps(json.loads(data.decode()), indent=2)
        raise ValueError(f"Unsupported export format: {format!r}")

    def export_cost_summary(
        self,
        tags: Optional[Dict[str, str]] = None,
        after: Optional[dt.datetime] = None,
        before: Optional[dt.datetime] = None,
    ) -> Dict[str, Any]:
        """Aggregate cost data across matching sessions."""
        summaries = self.list_sessions(tags=tags, after=after, before=before, limit=10_000)
        total_cost = sum(s.total_cost for s in summaries)
        return {
            "session_count": len(summaries),
            "total_cost_usd": round(total_cost, 6),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "tactic_name": s.tactic_name,
                    "state": s.state,
                    "cost_usd": s.total_cost,
                    "timestamp": s.timestamp,
                }
                for s in summaries
            ],
        }

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_session(self, session_id: str) -> None:
        """Remove session data and its index entry."""
        self._backend.delete(self._session_key(session_id))
        self._backend.delete(self._index_key(session_id))
        logger.debug("Deleted session %s", session_id)
