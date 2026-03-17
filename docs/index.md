# Welcome to LLLM

<p align="center">
  <img src="assets/LLLM-logo.png" alt="LLLM Logo" width="200"/>
</p>

**LLLM** (Low-Level Language Model) is a lightweight framework for building advanced agentic systems. Go from a 5-line prototype to a production multi-agent system without rewriting anything — just add structure as complexity grows.

---

## Quick Start

```python
from lllm import Tactic

# One-liner — no config, no setup
response = Tactic.quick("What is the capital of France?")
print(response.content)

# Or get the agent for multi-turn chat
agent = Tactic.quick(system_prompt="You are a helpful assistant.", model="gpt-4o")
agent.open("chat")
agent.receive("Hello!")
print(agent.respond().content)
```

No `lllm.toml`, no folder structure, no subclassing. [Full quick start →](getting-started.md)

---

## Learning Path

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **1 · Getting Started**

    ---

    Install LLLM and run your first agent in 5 lines. No config needed.

    [:octicons-arrow-right-24: Quick Start](getting-started.md)

-   :material-map:{ .lg .middle } **2 · Architecture Overview**

    ---

    How the four abstractions — Agent, Prompt, Dialog, Tactic — fit together, and where the package system fits in.

    [:octicons-arrow-right-24: Overview](architecture/overview.md)

-   :material-package-variant:{ .lg .middle } **3 · Package System**

    ---

    The organisational layer that makes projects beyond a single script work cleanly. Central to any real LLLM project.

    [:octicons-arrow-right-24: Package System](architecture/packages.md)

-   :material-school:{ .lg .middle } **4 · Tutorials (8 lessons)**

    ---

    From a one-liner chat to a production multi-agent system — step by step, no prior LLLM knowledge required.

    [:octicons-arrow-right-24: Start Lesson 1](tutorials/01-quick-start.md) · [:octicons-arrow-right-24: All lessons](tutorials/index.md)

-   :material-tune:{ .lg .middle } **5 · Advanced Patterns**

    ---

    Proxies, custom invokers, log backends, batch processing, streaming, and image input.

    [:octicons-arrow-right-24: Advanced Patterns](tutorials/08-advanced-patterns.md) · [:octicons-arrow-right-24: Logging](tutorials/07-logging.md)

-   :material-code-tags:{ .lg .middle } **API Reference**

    ---

    Auto-generated docs for Agent, Tactic, Prompt, Dialog, LogStore, and all public classes.

    [:octicons-arrow-right-24: Core API](reference/core.md)

</div>

---

## Core Abstractions

| Concept | Role | Analogy |
|---------|------|---------|
| **Agent** | System prompt + base model + call loop | A "caller" |
| **Prompt** | Template + parser + tools + handlers | A "function" |
| **Dialog** | Per-agent conversation state | Internal "mental state" |
| **Tactic** | Wires agents to prompts, orchestrates collaboration | A "program" |

See the [Architecture Overview](architecture/overview.md) for the full picture, including design philosophy and data flow.
