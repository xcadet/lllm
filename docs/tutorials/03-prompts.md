# Lesson 3 — Prompts and Structured Output

A `Prompt` is more than a string. It bundles the template, output parsing rules, tool declarations, and error-recovery handlers into a single reusable object. Learning to build good prompts is the key to reliable agents.

---

## Creating a Prompt

```python
from lllm import Prompt

# Minimal — just a path and a template string
p = Prompt(
    path="greet/system",
    prompt="You are a friendly assistant. Greet the user by name.",
)
```

The `path` is a human-readable identifier used for logging and the resource registry. It must be unique within a runtime.

---

## Template Variables

Use standard Python `str.format()` placeholders in the template:

```python
p = Prompt(
    path="analyst/system",
    prompt="You are an expert in {domain}. Today's date is {date}.",
)

# Render by calling the prompt
rendered = p(domain="machine learning", date="2026-03-17")
print(rendered)
# "You are an expert in machine learning. Today's date is 2026-03-17."
```

When you call `agent.open(alias, prompt_args={...})`, the `prompt_args` dict is forwarded to the system prompt's `__call__`. The same applies to `agent.receive_prompt(prompt, prompt_args={...})`.

```python
agent.open("session", prompt_args={"domain": "finance", "date": "2026-03-17"})
```

---

## Checking Template Variables

```python
print(p.template_vars)          # {"domain", "date"}
missing = p.validate_args({})   # ["domain", "date"]
```

This validation runs automatically at render time, giving you a clear error if you forget a variable.

---

## Structured Output with a Parser

For workflows that need the LLM to return data in a predictable format, attach a `DefaultTagParser`:

```python
from lllm.core.prompt import DefaultTagParser

p = Prompt(
    path="extractor/system",
    prompt="""
Extract the entities from the text and return them like this:

<people>comma-separated names</people>
<organizations>comma-separated org names</organizations>
""",
    parser=DefaultTagParser(
        xml_tags=["people", "organizations"],
        required_xml_tags=["people"],
    ),
)
```

After the LLM responds, `message.parsed` contains:

```python
{
    "raw": "<people>Alice, Bob</people><organizations>Acme Corp</organizations>",
    "xml_tags": {
        "people": ["Alice, Bob"],
        "organizations": ["Acme Corp"],
    },
    "md_tags": {},
    "signal_tags": {},
}
```

---

## Markdown Code Block Parsing

```python
p = Prompt(
    path="coder/system",
    prompt="Write the solution in a ```python code block.",
    parser=DefaultTagParser(
        md_tags=["python"],
        required_md_tags=["python"],
    ),
)
```

`message.parsed["md_tags"]["python"]` will be a list of extracted code blocks.

---

## Signal Tags

Signal tags let the model communicate binary intent:

```python
p = Prompt(
    path="classifier/system",
    prompt="""
Decide whether the review is positive. If yes, include <POSITIVE> in your response.
""",
    parser=DefaultTagParser(signal_tags=["POSITIVE"]),
)

# After respond():
is_positive = message.parsed["signal_tags"]["POSITIVE"]  # True / False
```

---

## Pydantic Structured Output

For JSON/structured output via the model's native format support:

```python
from pydantic import BaseModel
from lllm import Prompt

class Summary(BaseModel):
    headline: str
    key_points: list[str]
    sentiment: str

p = Prompt(
    path="summarizer/system",
    prompt="Summarize the following article: {article}",
    format=Summary,   # tell the invoker to use structured output mode
)
```

The LLM will be asked to emit valid JSON that matches `Summary`. The parsed model is available at `message.parsed`.

> **Note:** Structured output requires model support (OpenAI `gpt-4o` and compatible). Check your model's documentation.

---

## Writing a Custom Parser

Subclass `DefaultTagParser` and override `parse()` to add your own validation logic:

```python
from lllm.core.prompt import DefaultTagParser
from lllm.core.const import ParseError

class GraphParser(DefaultTagParser):
    def parse(self, content: str, **kwargs) -> dict:
        parsed = super().parse(content, **kwargs)
        # Detect cycles in the adjacency list
        edges = parsed["xml_tags"].get("edges", [])
        if self._has_cycle(edges):
            raise ParseError("The returned graph contains a cycle — please fix it.")
        return parsed

    def _has_cycle(self, edges): ...
```

When `parse()` raises `ParseError`, the agent loop automatically retries with an error message sent back to the model (see [Lesson 5](05-tactics.md) on the `max_exception_retry` setting).

---

## Prompt Inheritance with `extend()`

```python
base = Prompt(
    path="base/system",
    prompt="You are a helpful assistant working on {topic}.",
)

specialized = base.extend(
    path="specialized/system",
    prompt="You are a senior Python engineer working on {topic}. Always include type hints.",
)
```

`extend()` copies all fields and applies overrides. A new `path` is mandatory to keep identifiers unique.

---

## Loading Prompts from Files

In larger projects you store prompts as `.py` or `.md` files and auto-register them:

```python
# prompts/greeter.py
from lllm import Prompt

greeter_system = Prompt(
    path="greeter/system",
    prompt="You are a warm, friendly assistant. User's name: {name}.",
)
```

With auto-discovery configured in `lllm.toml`, this prompt becomes available anywhere via:

```python
from lllm import load_prompt
p = load_prompt("greeter/system")
```

See [Lesson 6](06-config-and-discovery.md) for the full auto-discovery setup.

---

## Summary

| Feature | How |
|---|---|
| Template variables | `{variable}` in the prompt string |
| Render manually | `prompt(var=value)` |
| XML tag parsing | `DefaultTagParser(xml_tags=[...])` |
| Markdown block parsing | `DefaultTagParser(md_tags=[...])` |
| Signal tags | `DefaultTagParser(signal_tags=[...])` |
| Pydantic output | `Prompt(format=MyModel)` |
| Custom validation | Subclass `DefaultTagParser`, override `parse()` |
| Prompt composition | `prompt.extend(path=..., ...)` |

**Next:** [Lesson 4 — Tools: Giving Agents Superpowers](04-tools.md)
