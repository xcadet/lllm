# Lesson 7 — Logging and Cost Tracking

Every tactic call produces a `TacticCallSession` that captures the complete execution trace: every LLM call, every tool interrupt, token counts, dollar costs, and failure tracebacks. The `LogStore` persists these sessions so you can query and analyse them later.

---

## Attaching a LogStore to a Tactic

```python
from lllm import LogStore, LocalFileBackend

store = LogStore(backend=LocalFileBackend(path="./logs"))

tactic = MyTactic(config, log_store=store)
```

From this point on, every call to `tactic(task)` automatically saves the session to `./logs/`. Without a `LogStore`, LLLM emits a one-time `UserWarning` to remind you.

---

## Backend Options

| Backend | Import | Best for |
|---|---|---|
| `LocalFileBackend` | `from lllm import LocalFileBackend` | Development, small projects |
| `SQLiteBackend` | `from lllm import SQLiteBackend` | Production, queryable store |
| `NoOpBackend` | `from lllm import NoOpBackend` | Tests, benchmarks |

```python
from lllm import SQLiteBackend, LogStore

store = LogStore(backend=SQLiteBackend(path="./runs.db"))
```

---

## Convenience Factories

```python
from lllm.logging import local_store, sqlite_store, noop_store

store = local_store("./logs")
store = sqlite_store("./runs.db")
store = noop_store()
```

These are thin wrappers that create the backend and `LogStore` in one call.

---

## Tagging Sessions

Tags are key-value strings you attach at call time to make sessions filterable:

```python
tactic(task, tags={"env": "prod", "experiment": "v2", "user": "alice"})
```

Tags are stored in the index and never require loading the full session data to filter.

---

## Listing Sessions

```python
sessions = store.list_sessions(
    tags={"experiment": "v2"},           # filter by tag
    state="success",                     # "success" | "failure" | "running"
    tactic_path="my_project::analyzer",  # filter by tactic
    limit=50,
)

for s in sessions:
    print(s.session_id, s.state, s.total_cost, s.timestamp)
```

Results are sorted newest-first. Each item is a `SessionSummary` — a lightweight object without full session data.

---

## Loading a Full Session

```python
session = store.load_session(session_id)

# Detailed breakdown
for agent_name, calls in session.agent_sessions.items():
    for call in calls:
        print(f"Agent: {agent_name}")
        print(f"  Tool interrupts: {len(call.interrupts)}")
        print(f"  Exception retries: {call.exception_retries_count}")
        print(f"  Cost: {call.cost}")
```

---

## Cost Aggregation

```python
# Cost for a specific tactic across all sessions
summary = store.export_cost_summary(
    tactic_path="my_project::analyzer",
    tags={"env": "prod"},
)

print(f"Sessions: {summary['session_count']}")
print(f"Total cost: ${summary['total_cost_usd']:.4f}")
```

For a single session:

```python
session = tactic(task, return_session=True)
print(session.total_cost.cost)            # total dollar cost
print(session.total_cost.prompt_tokens)   # input tokens
print(session.total_cost.completion_tokens)  # output tokens
```

---

## Debugging Failed Sessions

When a tactic call raises, the session records the full Python traceback:

```python
try:
    tactic(bad_input)
except Exception:
    pass

sessions = store.list_sessions(state="failure", limit=1)
record = store.load_session_record(sessions[0].session_id)
print(record.traceback)
```

---

## Exporting Sessions

```python
json_str = store.export_session(session_id, format="json")
with open("session_dump.json", "w") as f:
    f.write(json_str)
```

---

## Terminal Logging

Enable coloured terminal output for development:

```python
from lllm.logging import setup_logging
setup_logging(level="DEBUG")   # or "INFO", "WARNING"
```

This configures Python's standard `logging` module with a `ColoredFormatter` that highlights warnings and errors.

---

## Stable Tactic Identities

LLLM uses a **stable tactic path** of the form `"{package_name}::{tactic_name}"` (e.g. `"my_project::analyzer"`) as the canonical identifier for filtering. This identifier is:

- Independent of the file path inside the package
- Independent of `under` prefixes in `lllm.toml`
- Independent of package aliases

Only renaming the package in `lllm.toml` or renaming `Tactic.name` changes it. This means log queries remain valid even as you reorganise your project layout.

---

## Session Record Fields

| Field | Type | Description |
|---|---|---|
| `tactic_name` | `str` | Short tactic name |
| `tactic_path` | `str` | Stable qualified key |
| `state` | `str` | `"success"` / `"failure"` / `"running"` |
| `agent_sessions` | `dict` | Per-agent call traces |
| `sub_tactic_sessions` | `dict` | Nested tactic traces |
| `delivery` | `Any` | The final return value of `call()` |
| `total_cost` | `InvokeCost` | Aggregated cost |

---

## Summary

| Task | API |
|---|---|
| Create a local store | `local_store("./logs")` |
| Create an SQLite store | `sqlite_store("./runs.db")` |
| Attach to a tactic | `MyTactic(config, log_store=store)` |
| Tag a session | `tactic(task, tags={"k": "v"})` |
| List sessions | `store.list_sessions(tags=..., state=...)` |
| Load full session | `store.load_session(session_id)` |
| Aggregate costs | `store.export_cost_summary(tactic_path=...)` |
| Debug failures | `store.load_session_record(id).traceback` |

**Next:** [Lesson 8 — Advanced Patterns](08-advanced-patterns.md)
