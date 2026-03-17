# Building Agents

This guide walks through building an agentic system from scratch — starting with a single agent and progressively adding tools, multi-turn conversation, and multi-agent collaboration.

---

## Step 1: Single agent, one question

The simplest possible setup:

```python
from lllm import Tactic

agent = Tactic.quick("You are a helpful assistant.", model="gpt-4o")
agent.open("session")
agent.receive("What is the capital of France?")
print(agent.respond().content)
```

`Tactic.quick()` returns a bare `Agent` — no tactic subclassing needed for simple use cases.

---

## Step 2: Multi-turn conversation

Reuse the same dialog alias to continue a conversation:

```python
from lllm import Tactic

agent = Tactic.quick("You are a helpful assistant.", model="gpt-4o")
agent.open("chat")

while True:
    user_input = input("You: ")
    if user_input.lower() in ("exit", "quit"):
        break
    agent.receive(user_input)
    reply = agent.respond()
    print(f"Agent: {reply.content}")
```

The dialog accumulates messages across turns. Each call to `respond()` sees the full history.

---

## Step 3: Structured output

Use a Pydantic model as the output format:

```python
from pydantic import BaseModel
from lllm import Tactic
from lllm.core.prompt import Prompt

class Summary(BaseModel):
    headline: str
    key_points: list[str]
    sentiment: str

prompt = Prompt(
    path="summarizer/system",
    prompt="You are a document summarizer. Return structured JSON.",
    format=Summary,
)

agent = Tactic.quick(prompt, model="gpt-4o")
agent.open("work")
agent.receive("Article text goes here...")
result = agent.respond()
summary: Summary = result.parsed   # typed Pydantic object
print(summary.headline)
```

---

## Step 4: Adding tools

Link Python functions as tools the LLM can call:

```python
from lllm import Tactic
from lllm.core.prompt import Prompt, Function

def get_weather(city: str) -> str:
    # In practice, call a real weather API
    return f"Sunny, 22°C in {city}"

weather_fn = Function.from_callable(
    get_weather,
    description="Get the current weather for a city",
)

prompt = Prompt(
    path="assistant/system",
    prompt="You are a helpful assistant with access to weather data.",
    functions=[weather_fn],
)

agent = Tactic.quick(prompt, model="gpt-4o")
agent.open("session")
agent.receive("What's the weather like in Tokyo?")
response = agent.respond()
print(response.content)
```

The agent call loop automatically executes tool calls, collects results, and continues until the model produces a final text response.

---

## Step 5: Multi-agent tactic

For more complex tasks, subclass `Tactic` and orchestrate multiple agents:

```python
from lllm import Tactic

class ResearchWriter(Tactic):
    name = "research_writer"
    agent_group = ["researcher", "writer"]

    def call(self, topic: str, **kwargs) -> str:
        researcher = self.agents["researcher"]
        writer = self.agents["writer"]

        # Researcher gathers information
        researcher.open("research", prompt_args={"topic": topic})
        findings = researcher.respond()

        # Writer turns findings into prose
        writer.open("draft", prompt_args={"findings": findings.content, "topic": topic})
        return writer.respond().content
```

Wire it with a YAML config:

```yaml
# configs/research_writer.yaml
agent_group_configs:
  researcher:
    model_name: gpt-4o
    system_prompt_path: researcher_system
    temperature: 0.3
    max_completion_tokens: 4000
  writer:
    model_name: gpt-4o
    system_prompt_path: writer_system
    temperature: 0.7
```

Run it:

```python
from lllm import build_tactic, load_config

config = load_config("research_writer")
tactic = ResearchWriter(config, ckpt_dir="./runs")
result = tactic("The impact of quantum computing on cryptography")
print(result)
```

---

## Step 6: Batch and async execution

Run the same tactic over many inputs:

```python
topics = [
    "Quantum computing",
    "Large language models",
    "Neuromorphic chips",
]

# Sequential
results = [tactic(t) for t in topics]

# Parallel (thread pool)
results = tactic.bcall(topics, max_workers=3)

# Parallel with partial failure tolerance
results = tactic.bcall(topics, max_workers=3, fail_fast=False)
# items that failed are returned as Exception objects

# Async streaming (yields results as they complete, with original index)
async for idx, result in tactic.ccall(topics):
    print(f"[{idx}] {result}")
```

---

## Step 7: Session logging

Attach a log store to track costs, inputs, outputs, and traces:

```python
from lllm import build_tactic, load_config
from lllm.logging import local_store

config = load_config("research_writer")
store = local_store("./logs")

tactic = ResearchWriter(config, ckpt_dir="./runs")
result, session = tactic("Quantum computing", return_session=True)

store.save(session)
print(f"Cost: ${session.cost.total_cost:.4f}")
```

Query sessions later:

```python
sessions = store.list_sessions(tags=["research_writer"])
for s in sessions:
    print(s.session_id, s.cost.total_cost)
```

---

## Next Steps

- [Prompts](../core/prompts.md) — templates, parsers, and handlers in depth
- [Agent Call](../core/agent-call.md) — how the call loop handles errors and interrupts
- [Tactics](../core/tactic.md) — sub-tactics, typed I/O, and registration
- [Logging](../core/logging.md) — full logging system reference
- [Project Structure](project-template.md) — how to organise a larger project
