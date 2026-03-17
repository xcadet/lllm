# Lesson 8 — Advanced Patterns

This lesson brings together everything covered so far and introduces patterns for production-grade agentic systems: multi-proxy orchestration, dialog forking for exploration, structured multi-step pipelines, and parallel batch processing.

> **Proxy basics** (defining a `BaseProxy`, `exec_env: interpreter`, `run_python`, `CALL_API`) are covered in [Lesson 4 — Tools](04-tools.md#proxy-tools--structured-access-to-external-apis). This lesson assumes you are already comfortable with the single-proxy setup and shows more advanced compositions.

---

## Pattern 1: Multi-Proxy Orchestration

When an agent needs to combine data from several APIs, give it access to multiple proxies and let it drive the calls through a shared interpreter. Each proxy's endpoints are lazily discovered via `query_api_doc` so the context stays clean.

```yaml
# config.yaml
agent_configs:
  - name: research_analyst
    system_prompt: >
      You are a financial research analyst. You have access to market data,
      macroeconomic indicators, and news search. Use them together.
    proxy:
      activate_proxies: [fmp, fred, exa]   # three proxies loaded
      exec_env: interpreter
      max_output_chars: 8000
      timeout: 90.0
```

The agent's typical session for a complex query:

```python
# Turn 1: discover what the market data proxy exposes
query_api_doc("fmp")
# → endpoint list: price, earnings, balance-sheet, ...

# Turn 2: pull the data it needs
prices = CALL_API("fmp/price", {"symbol": "AAPL", "period": "1y"})
macro  = CALL_API("fred/series", {"series_id": "GDP"})
print(f"Got {len(prices)} price points, latest GDP: {macro[-1]['value']}")

# Turn 3: cross-reference with news
news = CALL_API("exa/search", {"query": "Apple earnings outlook 2025", "num_results": 5})
for article in news:
    print(article["title"], article["url"])
```

Variables persist across turns, so a complex analysis can be built incrementally over many `run_python` calls. The interpreter acts as a shared scratchpad across the whole session.

---

## Pattern 2: Dialog Forking for Hypothesis Exploration

Fork a dialog to explore multiple reasoning paths from the same conversation state, then pick the best outcome:

```python
from lllm import Tactic
from lllm.invokers import build_invoker
from lllm import Agent, Prompt

class HypothesisTactic(Tactic):
    name = "hypothesis_explorer"
    agent_group = ["analyst"]

    def call(self, task: str, hypotheses: list[str], **kwargs) -> str:
        analyst = self.agents["analyst"]

        # Establish shared context
        analyst.open("base")
        analyst.receive(f"Background context: {task}")
        analyst.respond()   # model acknowledges / asks clarifying questions

        results = {}
        for i, hypothesis in enumerate(hypotheses):
            # Fork from the shared base — each branch is independent
            analyst.fork("base", f"branch_{i}")
            analyst.receive(f"Now evaluate this hypothesis: {hypothesis}")
            results[hypothesis] = analyst.respond().content
            analyst.close(f"branch_{i}")   # clean up

        # Synthesize: bring everything back to base and decide
        analyst.switch("base")
        summary = "\n".join(f"- {h}: {r[:80]}..." for h, r in results.items())
        analyst.receive(f"Given these evaluations:\n{summary}\n\nWhich hypothesis is strongest?")
        return analyst.respond().content
```

---

## Pattern 3: Structured Multi-Step Pipeline with Pydantic

Use Pydantic models as the interface between pipeline stages for type safety:

```python
from pydantic import BaseModel
from lllm import Tactic, Prompt
from lllm.core.prompt import DefaultTagParser

class Plan(BaseModel):
    steps: list[str]
    risks: list[str]

class PipelineTactic(Tactic):
    name = "pipeline"
    agent_group = ["planner", "executor"]

    def call(self, task: str, **kwargs) -> str:
        planner = self.agents["planner"]
        executor = self.agents["executor"]

        # Stage 1: produce a structured plan
        planner.open("plan")
        planner.receive(task)
        plan_msg = planner.respond()

        # parse plan from XML tags
        steps = plan_msg.parsed["xml_tags"].get("step", [])
        risks = plan_msg.parsed["xml_tags"].get("risk", [])
        plan = Plan(steps=steps, risks=risks)

        # Stage 2: execute each step
        results = []
        for step in plan.steps:
            executor.open(f"step_{len(results)}")
            executor.receive(f"Execute: {step}")
            results.append(executor.respond().content)
            executor.close(f"step_{len(results) - 1}")

        return "\n".join(results)
```

The planner prompt uses a parser that extracts `<step>` and `<risk>` XML tags:

```python
planner_prompt = Prompt(
    path="pipeline/planner",
    prompt="""
Create a plan for: {task}

Format each step as <step>description</step>
Format each risk as <risk>description</risk>
""",
    parser=DefaultTagParser(xml_tags=["step", "risk"]),
)
```

---

## Pattern 4: High-Throughput Batch Processing

Process thousands of items concurrently using `bcall`:

```python
from lllm import LogStore
from lllm.logging import sqlite_store

store = sqlite_store("./batch_runs.db")
tactic = ClassificationTactic(config, log_store=store)

items = load_your_dataset()   # list of strings

# Process 50 items in parallel, fail fast on first error
results = tactic.bcall(
    items,
    max_workers=50,
    fail_fast=True,
    tags={"batch": "2026-03-17", "env": "prod"},
)

# Collect errors without stopping the batch
results = tactic.bcall(items, max_workers=50, fail_fast=False)
for i, r in enumerate(results):
    if isinstance(r, Exception):
        print(f"Item {i} failed: {r}")
    else:
        print(f"Item {i}: {r}")
```

---

## Pattern 5: Streaming Responses

Pass a `stream_handler` to the `Agent` to receive tokens as they are generated:

```python
from lllm.invokers.base import BaseStreamHandler

class PrintStreamHandler(BaseStreamHandler):
    def on_token(self, token: str) -> None:
        print(token, end="", flush=True)

    def on_done(self) -> None:
        print()   # newline after streaming finishes

from lllm.invokers import build_invoker
from lllm import Agent, Prompt

invoker = build_invoker({"invoker": "litellm"})
agent = Agent(
    name="streamer",
    system_prompt=Prompt(path="s/system", prompt="You are a storyteller."),
    model="gpt-4o",
    llm_invoker=invoker,
    stream_handler=PrintStreamHandler(),
)

agent.open("chat")
agent.receive("Tell me a short story about a robot.")
agent.respond()   # tokens print to stdout as they arrive
```

---

## Pattern 6: Custom Exception and Interrupt Handlers

Override the default retry prompts by subclassing `DefaultSimpleHandler`:

```python
from lllm.core.prompt import DefaultSimpleHandler, Prompt, AgentCallSession

class VerboseHandler(DefaultSimpleHandler):
    def on_exception(self, prompt: Prompt, session: AgentCallSession) -> Prompt:
        retry_num = session.exception_retries_count
        return prompt.extend(
            path=f"__verbose_exception_{retry_num}",
            prompt=(
                f"Attempt {retry_num + 1}: Your previous response had an error: "
                "{{error_message}}. Please fix it and try again. "
                "Pay close attention to the required format."
            ),
        )

my_prompt = Prompt(
    path="strict_agent/system",
    prompt="You are a strict JSON generator. {task}",
    handler=VerboseHandler(),
)
```

The `session` object gives you access to all prior retries, interrupt counts, and LLM-recall history so you can write handlers that adapt their strategy over time.

---

## Pattern 7: Image Input

Agents support multimodal conversations:

```python
agent.open("vision")
agent.receive_image("/path/to/chart.png", caption="Q1 revenue chart")
agent.receive("What trends do you see in this chart?")
response = agent.respond()
print(response.content)
```

`receive_image` accepts a file path, a PIL `Image` object, or a base64-encoded string.

---

## Architectural Summary

```
lllm.toml                  ← project declaration
├── prompts/               ← Prompt objects (auto-discovered)
├── configs/               ← YAML agent configs (auto-discovered)
├── tactics/               ← Tactic subclasses (auto-discovered)
└── proxies/               ← BaseProxy subclasses (auto-discovered)

Runtime                    ← registry (prompts, tactics, configs, proxies)
└── default / named

Tactic                     ← orchestration logic
└── call(task) → result
    └── Agent(s)           ← LLM identity
        └── Dialog(s)      ← append-only conversation history
            └── Prompt     ← template + parser + tools + handlers

LogStore                   ← persistence
└── TacticCallSession      ← per-call trace (cost, interrupts, errors)
```

---

## Putting It All Together

```python
from lllm import load_package, resolve_config, build_tactic
from lllm.logging import sqlite_store

# Bootstrap the project
load_package()                            # reads lllm.toml, discovers everything

# Build a production tactic
store = sqlite_store("./production.db")
config = resolve_config("default")        # loads and merges configs/default.yaml
tactic = build_tactic(config, log_store=store)

# Run a batch with tags for observability
results = tactic.bcall(
    my_tasks,
    max_workers=20,
    tags={"version": "1.2", "env": "prod"},
)
```

---

## What to Explore Next

- **Proxy basics** — defining proxies and the interpreter tool loop: [Lesson 4 — Tools](04-tools.md#proxy-tools--structured-access-to-external-apis).
- **Computer Use Agent** — `lllm.tools.cua` for browser automation via Playwright.
- **Responses API** — set `api_type = "response"` per agent to enable native OpenAI web search.
- **Skills** — higher-level reusable agent behaviours (see the [Skills](https://agentskills.io) documentation).
- **Analysis GUI** — the roadmap includes a Streamlit/Dash dashboard for the `LogStore` database.
