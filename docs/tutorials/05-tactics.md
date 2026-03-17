# Lesson 5 — Tactics: Coordinating Multiple Agents

A **Tactic** is the top-level unit of work in LLLM. It is a class that:

- Declares which agents it needs (`agent_group`)
- Implements `call()` to orchestrate those agents
- Handles per-call isolation, session tracking, and logging automatically

Think of it as an `nn.Module` for agents: composable, stateless between calls, and easy to test.

---

## Defining a Tactic

```python
from lllm import Tactic, Prompt
from lllm.invokers import build_invoker
from lllm import Agent

class SummarizerTactic(Tactic):
    name = "summarizer"
    agent_group = ["writer"]

    def call(self, task: str, **kwargs) -> str:
        writer = self.agents["writer"]

        writer.open("session")
        writer.receive(f"Summarize this text in 3 bullet points:\n\n{task}")
        response = writer.respond()

        return response.content
```

Every tactic **must** define:
- `name` — a unique string identifier (used in the registry and logs)
- `agent_group` — a list of agent names that must appear in the config
- `call(task, **kwargs)` — the orchestration logic

`self.agents` is a dict of ready-to-use `Agent` instances, one per name in `agent_group`. They are re-created fresh for every call, so concurrent calls are safe.

---

## Configuring a Tactic

Tactics receive a `config` dict at construction time. The standard format:

```python
config = {
    "tactic_type": "summarizer",
    "global": {
        "model_name": "gpt-4o",
        "model_args": {"temperature": 0.2},
    },
    "agent_configs": [
        {
            "name": "writer",
            "system_prompt": "You are a concise technical writer.",
            "model_args": {"max_completion_tokens": 1000},
        },
    ],
}
```

`global` provides defaults merged into every agent config. Per-agent `model_args` override the global ones.

---

## Calling a Tactic

```python
tactic = SummarizerTactic(config)

result = tactic("Large bodies of text about machine learning concepts...")
print(result)
```

Calling `tactic(task)` runs `_execute()` internally, which:
1. Creates fresh agent instances.
2. Wraps them in `_TrackedAgent` proxies for session recording.
3. Calls `call(task)`.
4. Captures cost, agent call counts, success/failure state.
5. Returns the result (or raises).

---

## Multi-Agent Tactic

Here is a tactic that uses two agents in sequence:

```python
class ResearchTactic(Tactic):
    name = "researcher"
    agent_group = ["finder", "synthesizer"]

    def call(self, task: str, **kwargs) -> str:
        finder = self.agents["finder"]
        synthesizer = self.agents["synthesizer"]

        # Step 1: gather raw facts
        finder.open("gather")
        finder.receive(f"List 5 key facts about: {task}")
        facts = finder.respond().content

        # Step 2: synthesize into a coherent paragraph
        synthesizer.open("synthesize")
        synthesizer.receive(f"Facts:\n{facts}\n\nWrite a short paragraph.")
        return synthesizer.respond().content

config = {
    "tactic_type": "researcher",
    "global": {"model_name": "gpt-4o"},
    "agent_configs": [
        {"name": "finder", "system_prompt": "You gather accurate factual information."},
        {"name": "synthesizer", "system_prompt": "You write clear, concise summaries."},
    ],
}

tactic = ResearchTactic(config)
print(tactic("quantum computing"))
```

---

## Session Tracking

Every call automatically produces a `TacticCallSession`:

```python
session = tactic("quantum computing", return_session=True)

print(session.state)              # "success" or "failure"
print(session.total_cost.cost)    # dollar cost (float)
print(session.agent_call_count)   # number of LLM calls made
print(session.summary())          # compact dict overview
```

The session records every agent call, every tool interrupt, and any errors. It is designed for debugging and cost analysis.

---

## Sub-Tactic Composition

Tactics can compose other tactics, just like functions calling functions:

```python
class PipelineTactic(Tactic):
    name = "pipeline"
    agent_group = ["coordinator"]

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        # Declare a sub-tactic; sessions are tracked automatically
        self.researcher = ResearchTactic(config)

    def call(self, task: str, **kwargs) -> str:
        # Call the sub-tactic
        facts = self.researcher(task)

        coordinator = self.agents["coordinator"]
        coordinator.open("plan")
        coordinator.receive(f"Based on this research:\n{facts}\n\nCreate an action plan.")
        return coordinator.respond().content
```

Sub-tactics assigned as attributes (`self.researcher = ...`) are automatically registered in `self.sub_tactics` and their sessions are folded into the parent session for cost aggregation.

---

## Batch and Async Execution

Run many tasks in parallel using thread pools:

```python
tasks = ["topic A", "topic B", "topic C", "topic D"]

# Synchronous batch (thread pool)
results = tactic.bcall(tasks, max_workers=4)

# Async (for use inside an async framework)
import asyncio
result = asyncio.run(tactic.acall("single async task"))

# Async streaming results as they complete
async def run():
    async for idx, result in tactic.ccall(tasks, max_workers=4):
        print(f"Task {idx} done: {result}")

asyncio.run(run())
```

`bcall` uses `concurrent.futures.ThreadPoolExecutor`. Each task gets its own fresh agent instances, so there are no shared-state collisions.

---

## Auto-Registration

Defining a subclass automatically registers it with the default runtime:

```python
class MyTactic(Tactic):
    name = "my_tactic"
    agent_group = ["agent_a"]
    ...

# Now available via:
from lllm import build_tactic
t = build_tactic(config, name="my_tactic")
```

You can opt out of registration:

```python
class MyTactic(Tactic, register=False):
    ...
```

---

## Summary

| Concept | API |
|---|---|
| Define a tactic | `class MyTactic(Tactic): name=...; agent_group=[...]` |
| Implement logic | `def call(self, task, **kwargs) -> str` |
| Access agents | `self.agents["agent_name"]` |
| Call a tactic | `tactic(task)` |
| Get session | `tactic(task, return_session=True)` |
| Batch calls | `tactic.bcall(tasks, max_workers=N)` |
| Async call | `await tactic.acall(task)` |
| Compose tactics | `self.sub_tactic = OtherTactic(config)` |

**Next:** [Lesson 6 — Configuration and Auto-Discovery](06-config-and-discovery.md)
