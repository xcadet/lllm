# Getting Started

## Installation

```bash
pip install lllm-core
```

Set your LLM provider API key:

```bash
export OPENAI_API_KEY=sk-...        # OpenAI
# or
export ANTHROPIC_API_KEY=sk-ant-... # Anthropic
# or any other LiteLLM-supported provider
```

---

## 5-Line Quick Start

No config files. No folder structure. No subclassing.

```python
from lllm import Tactic

agent = Tactic.quick("You are a helpful assistant.", model="gpt-4o")
agent.open("chat")
agent.receive("What is the capital of France?")
print(agent.respond().content)
```

`Tactic.quick()` creates an agent from a plain string system prompt. The `open / receive / respond` pattern maps to: start a conversation, add a message, get a reply.

To use Anthropic instead:

```python
agent = Tactic.quick("You are a helpful assistant.", model="claude-opus-4-6")
```

LiteLLM handles all provider differences automatically.

---

## Growing Your Project

LLLM is designed so you can start simple and add structure only when you need it. The progression looks like this:

### Stage 1 — Single file, no config

Everything inline. Good for experiments and one-off scripts.

```python
from lllm import Tactic

agent = Tactic.quick("You are a helpful assistant.", model="gpt-4o")
agent.open("session1")
agent.receive("Summarize quantum computing in two sentences.")
print(agent.respond().content)
```

### Stage 2 — Add an `lllm.toml`

Once you have more than one prompt or want auto-discovery, add a config file:

```bash
cp lllm.toml.example lllm.toml
```

Edit it to point at your folders:

```toml
[package]
name = "my_project"
version = "0.1.0"

[prompts]
paths = ["prompts/"]
```

Then move prompts to `.md` files — they auto-register at startup:

```
my_project/
├── lllm.toml
├── prompts/
│   └── assistant_system.md   ← your system prompt
└── main.py
```

Load a prompt by name:

```python
from lllm import load_prompt

prompt = load_prompt("assistant_system")
agent = Tactic.quick(prompt, model="gpt-4o")
```

### Stage 3 — YAML agent configs

When you have multiple agents, describe them in YAML:

```yaml
# configs/my_tactic.yaml
agent_group_configs:
  researcher:
    model_name: gpt-4o
    system_prompt_path: researcher_system
    temperature: 0.3
  writer:
    model_name: gpt-4o
    system_prompt_path: writer_system
```

### Stage 4 — Subclass `Tactic`

Orchestrate multi-agent logic by implementing `call()`:

```python
from lllm import Tactic

class ResearchWriter(Tactic):
    name = "research_writer"
    agent_group = ["researcher", "writer"]

    def call(self, topic: str, **kwargs) -> str:
        researcher = self.agents["researcher"]
        writer = self.agents["writer"]

        researcher.open("research", prompt_args={"topic": topic})
        findings = researcher.respond()

        writer.open("write", prompt_args={"findings": findings.content})
        return writer.respond().content
```

See the [Building Agents guide](guides/building-agents.md) for a complete walkthrough, and [Project Structure](guides/project-template.md) for the recommended folder layout.

---

## Next Steps

- [Architecture Overview](architecture/overview.md) — understand how the pieces fit
- [Agent Call](core/agent-call.md) — deep dive into the agent call loop
- [Prompts](core/prompts.md) — templates, parsers, tools, and handlers
- [Tactics](core/tactic.md) — composing multi-agent systems
- [Config & Discovery](core/config.md) — `lllm.toml` and YAML configs
- [Logging](core/logging.md) — session tracking and replay
