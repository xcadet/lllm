# Lesson 4 — Tools: Giving Agents Superpowers

Tools let an agent call Python functions during a conversation. The LLM decides when to invoke a tool, receives the result, and continues reasoning. LLLM handles the interrupt loop automatically.

---

## The `@tool` Decorator

The fastest way to define a tool is with the `@tool` decorator:

```python
from lllm.core.prompt import tool

@tool(
    description="Get the current weather for a city",
    prop_desc={
        "city": "The city name, e.g. 'Paris'",
        "unit": "Temperature unit: 'celsius' or 'fahrenheit'",
    },
)
def get_weather(city: str, unit: str = "celsius") -> str:
    # Replace with a real API call
    return f"Sunny, 22°C in {city}"
```

`@tool` inspects the function signature to build the JSON Schema that gets sent to the model. Type hints map to JSON types:

| Python | JSON |
|---|---|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| `list` | `"array"` |
| `dict` | `"object"` |

Parameters without defaults are marked as `required` automatically.

---

## Attaching Tools to a Prompt

```python
from lllm import Prompt

weather_prompt = Prompt(
    path="weather_bot/system",
    prompt="You are a weather assistant. Use your tools to answer questions.",
    function_list=[get_weather],   # list of Function objects
)
```

When the agent uses this prompt, the model sees the tool schema and can call `get_weather`.

---

## Full Example: Weather Bot

```python
from lllm import Tactic
from lllm.core.prompt import tool, Prompt
from lllm.invokers import build_invoker
from lllm import Agent

@tool(description="Get current weather for a city")
def get_weather(city: str, unit: str = "celsius") -> str:
    return f"Sunny, 22°C in {city}"

weather_prompt = Prompt(
    path="weather_bot/system",
    prompt="You are a weather assistant.",
    function_list=[get_weather],
)

invoker = build_invoker({"invoker": "litellm"})
agent = Agent(
    name="weather_bot",
    system_prompt=weather_prompt,
    model="gpt-4o",
    llm_invoker=invoker,
    max_interrupt_steps=3,   # allow up to 3 tool calls per response
)

agent.open("chat")
agent.receive("What is the weather in Paris and Tokyo?")
response = agent.respond()
print(response.content)
```

The agent loop:
1. LLM sees the user question and decides to call `get_weather(city="Paris")`.
2. LLLM executes the function and feeds the result back.
3. LLM calls `get_weather(city="Tokyo")`.
4. LLLM executes and feeds back.
5. LLM writes the final answer.
6. `respond()` returns it.

---

## Controlling the Tool-Call Loop

```python
agent = Agent(
    ...
    max_interrupt_steps=5,   # maximum tool calls before forcing a final answer
    max_exception_retry=3,   # maximum retries when the model output fails validation
)
```

- `max_interrupt_steps=0` means unlimited (up to 100). Avoid this in production — always set an explicit cap.
- When the limit is reached, the agent appends a message asking the model to stop calling tools and write a final answer.

---

## Custom Result Formatting

By default the tool result is formatted as:

```
Return of calling function get_weather with arguments {'city': 'Paris', 'unit': 'celsius'}:
---
Sunny, 22°C in Paris
---
```

You can override this with a custom `processor`:

```python
def my_processor(result, function_call):
    return f"[{function_call.name}] → {result}"

@tool(description="Get weather", processor=my_processor)
def get_weather(city: str) -> str:
    return "Sunny"
```

---

## Building a `Function` Manually

For tools with complex schemas or when you want to declare the schema separately from the implementation:

```python
from lllm import Prompt
from lllm.core.prompt import Function

search_fn = Function(
    name="web_search",
    description="Search the web for information",
    properties={
        "query": {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "description": "Max results (default 5)"},
    },
    required=["query"],
)

# Attach the implementation separately
search_fn.link_function(lambda query, max_results=5: f"Top {max_results} results for '{query}'")

my_prompt = Prompt(
    path="research_bot/system",
    prompt="You are a research assistant.",
    function_list=[search_fn],
)
```

---

## MCP Servers

For tools exposed via the Model Context Protocol (MCP):

```python
from lllm.core.prompt import MCP, Prompt

mcp_server = MCP(
    server_label="my_tools",
    server_url="http://localhost:8080",
    require_approval="never",
    allowed_tools=["search", "fetch_url"],
)

my_prompt = Prompt(
    path="agent/system",
    prompt="You are an assistant with web access.",
    mcp_servers_list=[mcp_server],
)
```

> **Note:** MCP support requires an MCP-compatible invoker. Check the [Invokers reference](../reference/invokers.md) for details.

---

## Repeated Tool Call Detection

If the agent calls the same tool with the same arguments twice in one turn, LLLM detects the repetition and injects a warning telling the model not to call it again. This prevents infinite loops caused by a confused model.

---

## Error Handling in Tools

If your tool function raises an exception, LLLM catches it and feeds the error message back to the model as the tool result:

```python
@tool(description="Divide two numbers")
def divide(a: float, b: float) -> str:
    if b == 0:
        raise ValueError("Division by zero")
    return str(a / b)
```

The model sees `"Error: Division by zero"` as the result and can decide how to proceed (e.g., ask for different arguments).

---

## Summary

| Concept | API |
|---|---|
| Define a tool | `@tool(description=..., prop_desc={...})` |
| Attach to prompt | `Prompt(function_list=[my_fn])` |
| Control loop depth | `Agent(max_interrupt_steps=N)` |
| Custom result format | `@tool(processor=my_fn)` |
| Manual schema | `Function(name=..., properties={...})` |
| MCP server | `Prompt(mcp_servers_list=[MCP(...)])` |

**Next:** [Lesson 5 — Tactics: Coordinating Multiple Agents](05-tactics.md)
