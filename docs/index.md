# Welcome to LLLM

<p align="center">
  <img src="assets/LLLM-logo.png" alt="LLLM Logo" width="200"/>
</p>

**LLLM** (Low-Level Language Model) is a lightweight framework for building advanced agentic systems. It lets you go from a 5-line prototype to a large multi-agent system without rewriting anything — just gradually adding structure as complexity grows.

---

## Why LLLM?

Most agentic frameworks either hide too much (making customization painful) or expose too much (requiring boilerplate from the start). LLLM sits in between:

- **Start in 5 lines** — no config files, no folder structure, no subclassing required
- **Grow incrementally** — add `lllm.toml`, prompt files, YAML configs only when you need them
- **Stay in control** — the code is plain and readable; no magic, no hidden state
- **Build composable systems** — Tactics are reusable library modules that can be shared and imported like packages

---

## Core Abstractions

| Concept | Role | Analogy |
|---------|------|---------|
| **Agent** | System prompt + base model + call loop | A "caller" |
| **Prompt** | Template + parser + tools + handlers | A "function" |
| **Dialog** | Per-agent conversation state | Internal "mental state" |
| **Tactic** | Wires agents to prompts, orchestrates collaboration | A "program" |

---

## 5-Line Quick Start

```python
from lllm import Tactic

agent = Tactic.quick("You are a helpful assistant.", model="gpt-4o")
agent.open("chat")
agent.receive("What is the capital of France?")
print(agent.respond().content)
```

No `lllm.toml`, no folder structure, no subclassing. See [Getting Started](getting-started.md) to go further.

---

## Navigation

- **[Getting Started](getting-started.md)** — Installation, quick start, and how to grow your project
- **[Architecture Overview](architecture/overview.md)** — How the components fit together
- **Core Concepts** — Deep dives into each abstraction (Agent Call, Prompts, Dialogs, Tactics, …)
- **Guides** — Step-by-step tutorials for building real systems
- **API Reference** — Auto-generated API docs and module index
