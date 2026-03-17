# Lesson 1 — Quick Start: Your First Chat in 5 Lines

**Prerequisite:** Python 3.10+, an OpenAI or Anthropic API key.

---

## Installation

```bash
pip install lllm-core
```

Set your API key in the environment:

```bash
export OPENAI_API_KEY=sk-...
# or
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## One-Line Chat

```python
from lllm import Tactic

response = Tactic.quick("What is the capital of France?")
print(response.content)   # "Paris"
```

`Tactic.quick()` is the zero-config entry point. It creates a temporary agent, sends the message, and returns the response as a `Message` object. The `.content` attribute holds the plain text reply.

---

## Choosing a Model

```python
response = Tactic.quick(
    "Explain quantum entanglement in one sentence.",
    model="claude-opus-4-6",   # any LiteLLM model string
)
print(response.content)
```

LLLM uses [LiteLLM](https://github.com/BerriAI/litellm) under the hood, so you can pass any model identifier from that catalog — GPT-4o, Claude, Mistral, Gemini, etc.

---

## Custom System Prompt

```python
response = Tactic.quick(
    "What is 2 + 2?",
    system_prompt="You are a grumpy math teacher who always sighs before answering.",
)
print(response.content)
```

The `system_prompt` string is converted into a `Prompt` object automatically. You will learn more about `Prompt` in [Lesson 3](03-prompts.md).

---

## Getting the Agent Back

Sometimes you want to reuse the agent for follow-up messages:

```python
response, agent = Tactic.quick(
    "What is the capital of France?",
    return_agent=True,
)
print(response.content)
print(agent.name)   # "assistant"
```

Or get an agent without sending any query first:

```python
agent = Tactic.quick(system_prompt="You are a helpful assistant.", model="gpt-4o")
# … set up the dialog later
agent.open("chat")
agent.receive("What is the capital of France?")
print(agent.respond().content)
```

This pattern — `open` → `receive` → `respond` — is the foundation for everything in LLLM. [Lesson 2](02-agents-and-dialogs.md) covers it in depth.

---

## What `Tactic.quick` Does Internally

```
Tactic.quick(query, system_prompt, model)
  ├── builds a Prompt from system_prompt string
  ├── builds a LiteLLM invoker
  ├── creates an Agent(name="assistant", model=model, ...)
  ├── calls agent.open("chat")
  ├── calls agent.receive(query)
  └── returns agent.respond()
```

There is no config file, no folder structure, and no subclassing needed for this path. All of that is optional and covered in later lessons.

---

## Supported Providers

| Provider | Model example | Environment variable |
|---|---|---|
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `claude-opus-4-6` | `ANTHROPIC_API_KEY` |
| Mistral | `mistral/mistral-large` | `MISTRAL_API_KEY` |
| Any other | see LiteLLM docs | provider-specific |

---

## Summary

- `pip install lllm-core` + set an API key is all the setup needed.
- `Tactic.quick(query)` gives you a one-liner LLM call.
- The response is a `Message` object; `.content` is the text.
- Pass `return_agent=True` to get the `Agent` back for follow-up turns.

**Next:** [Lesson 2 — Agents and Dialogs](02-agents-and-dialogs.md)
