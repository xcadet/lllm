# Architecture Overview

LLLM organises an agentic system into four layers. Each layer has a single, clear responsibility and they compose cleanly.

```
┌──────────────────────────────────────────────────┐
│                    Tactic                        │  ← "the program"
│  (orchestrates agents, owns the task interface)  │
├────────────────┬────────────────┬────────────────┤
│    Agent A     │    Agent B     │    Agent C     │  ← "the callers"
│  (model+loop)  │  (model+loop)  │  (model+loop)  │
├────────────────┴────────────────┴────────────────┤
│               Prompts (functions)                │  ← "the calls"
│  template · parser · tools · handlers            │
├──────────────────────────────────────────────────┤
│               Dialogs (state)                    │  ← "mental state"
│  per-agent message history, fork-able tree       │
└──────────────────────────────────────────────────┘
```

---

## The Four Abstractions

### Tactic — the program

A `Tactic` is the top-level unit of an agentic system. It:

- Accepts a task (string or Pydantic model) and returns a result
- Owns a group of agents and wires them together
- Is **stateless** — each `tactic(task)` call spins up fresh agent instances
- Can be subclassed, shared, and reused like a library module

```python
class Analytica(Tactic):
    name = "analytica"
    agent_group = ["analyzer", "synthesizer"]

    def call(self, task: str) -> str:
        ...
```

### Agent — the caller

An `Agent` holds a system prompt and a model. It executes prompts through a **call loop** that handles:

- Retries on LLM errors
- Exception handling (parsing failures, bad output)
- Interrupt handling (tool calls, multi-step reasoning)

An agent is **not** a long-running process — it operates on a `Dialog` (conversation state) that the tactic manages.

```python
agent.open("dialog_alias")    # create/attach a dialog
agent.receive("user message") # append user turn
response = agent.respond()    # run the call loop, return Message
```

### Prompt — the function

A `Prompt` is the specification for a single agent turn:

- **Template** — string or `.md` file with `{variable}` slots
- **Parser** — extracts structured output from the raw LLM text
- **Tools** — callable Python functions linked to the prompt's tool schema
- **Handlers** — `on_exception` and `on_interrupt` prompts for the call loop

Prompts compose: one prompt can `extend()` another, inheriting its tools and parser.

### Dialog — the mental state

A `Dialog` is the per-agent conversation history. Key properties:

- **Append-only** — messages are never mutated after appending
- **Fork-able** — `dialog.fork()` creates a branch at any point, enabling parallel reasoning paths or exception-recovery sub-dialogs
- **Tree structure** — forks form a tree; the agent always works on the active branch

Each agent maintains its own dialog. Agents don't share dialogs — they share *information* by passing content between them in the tactic's `call()` method.

---

## Data Flow

```
tactic(task)
  │
  ├─► Agent A
  │     dialog.put_text(task)
  │     agent.respond()
  │       └─► agent call loop
  │             ├─► llm_invoker.call(dialog)   # API call
  │             ├─► parse output               # Prompt.parser
  │             ├─► handle tool calls          # Prompt.tools
  │             └─► return Message
  │
  └─► Agent B
        dialog.put_text(agent_a_result)
        agent.respond()
          └─► ...
```

---

## Configuration & Discovery

For projects beyond a single script, LLLM uses a `lllm.toml` manifest to declare resources:

```
project/
├── lllm.toml           ← declares prompt/proxy/config folders
├── prompts/            ← .md files auto-register as Prompt resources
├── configs/            ← .yaml files auto-register as agent configs
├── tactics/            ← .py files with Tactic subclasses auto-register
└── proxies/            ← .py files with BaseProxy subclasses auto-register
```

Resources are loaded lazily into a **Runtime** registry and accessed by name:

```python
prompt = runtime.get_prompt("my_prompt")
config = runtime.get_config("my_tactic")
```

Multiple named runtimes can coexist for parallel experiments or isolated tests.

---

## Design Principles

**1. Low-level by default.** LLLM stops at `Tactic` as its highest abstraction. Higher-level orchestration (system of systems, agent networks) is left to the application layer.

**2. Configuration as declaration.** System shape is described in TOML/YAML data, not hardcoded. This makes systems inspectable, shareable, and reproducible.

**3. Minimise hidden state.** Each call to `tactic(task)` is fresh. Dialogs are explicit objects you pass around. Nothing happens behind the scenes.

**4. Composable and package-friendly.** Tactics, prompts, proxies, and configs are independent modules. The `lllm.toml` package system lets you depend on and share these modules like Python packages.

---

## Where to Go Next

- [Agent Call](../core/agent-call.md) — the call loop in detail
- [Prompts](../core/prompts.md) — templates, parsers, tools, handlers
- [Dialogs](../core/dialog.md) — message state and forking
- [Tactics](../core/tactic.md) — orchestration patterns
- [Config & Discovery](../core/config.md) — `lllm.toml` and YAML configs
- [Packages](../core/packages.md) — namespacing and dependency management
