# Tutorials

A progressive series of 8 lessons that takes you from a one-line chat to a production-grade multi-agent system.

---

| # | Lesson | What you will learn |
|---|---|---|
| 1 | [Quick Start](01-quick-start.md) | Install, set an API key, send your first message |
| 2 | [Agents and Dialogs](02-agents-and-dialogs.md) | Core mental model: `Agent`, `Dialog`, multi-turn conversations, forking |
| 3 | [Prompts and Structured Output](03-prompts.md) | Template variables, XML/Markdown parsers, Pydantic output, prompt inheritance |
| 4 | [Tools](04-tools.md) | `@tool` decorator, attaching tools to prompts, tool-call loop, MCP servers |
| 5 | [Tactics](05-tactics.md) | Orchestrating multiple agents, session tracking, batch and async execution |
| 6 | [Configuration and Auto-Discovery](06-config-and-discovery.md) | `lllm.toml`, YAML agent configs, config inheritance, named runtimes |
| 7 | [Logging and Cost Tracking](07-logging.md) | `LogStore`, backends, tagging, cost aggregation, debugging failures |
| 8 | [Advanced Patterns](08-advanced-patterns.md) | Proxies, dialog forking, pipelines, batch processing, streaming, image input |

---

## Prerequisites

- Python 3.10+
- `pip install lllm-core`
- An API key for OpenAI (`OPENAI_API_KEY`) or Anthropic (`ANTHROPIC_API_KEY`)

---

## How to Read These Tutorials

Each lesson builds on the previous one. If you are new to LLLM, read them in order. If you are looking for a specific feature, the table above tells you which lesson covers it.

Code blocks are self-contained and runnable. Replace placeholder API calls (e.g. weather data) with real implementations when adapting examples to your project.
