# Lesson 9 — Proxy Tool Calling & the Agent Interpreter

This lesson covers LLLM's proxy-based tool-calling system: how to give an agent direct access to external APIs through a persistent Python interpreter that the agent drives with `run_python` calls.

---

## What this covers

- Defining a proxy with `@ProxyRegistrator` and `@BaseProxy.endpoint`
- Configuring `exec_env: interpreter` to wire the interpreter automatically
- How `run_python`, `CALL_API`, and `query_api_doc` work together
- State persistence across multiple `run_python` calls
- Truncation, timeout, and output capture behaviour
- When to use Jupyter mode instead of interpreter mode

---

## The problem: agents and external APIs

Agents need external data — market prices, web search, database queries, weather. The naive approach is to give the agent one tool per endpoint, but this doesn't scale: dozens of endpoints means dozens of tool definitions and a bloated context.

LLLM's proxy system solves this with two tools:

- **`query_api_doc(proxy_name)`** — retrieve full endpoint documentation on demand
- **`run_python(code)`** — execute Python in a persistent interpreter with `CALL_API` pre-injected

The agent learns the endpoint structure lazily (just-in-time via `query_api_doc`), then calls whatever it needs through `CALL_API` in Python. All of this happens inside the normal agent dialog loop — no extra tactic wiring needed.

---

## Step 1: Define a proxy

A proxy wraps an API surface. Endpoints are declared with `@BaseProxy.endpoint` — this metadata drives the API directory, `query_api_doc` responses, and auto-testing.

```python
from lllm.proxies import BaseProxy, ProxyRegistrator

@ProxyRegistrator(
    path="weather",
    name="Weather API",
    description="Current weather and forecasts for any city.",
)
class WeatherProxy(BaseProxy):

    @BaseProxy.endpoint(
        category="current",
        endpoint="conditions",
        description="Current temperature and conditions for a city.",
        params={
            "city*": (str, "London"),         # * = required
            "units": (str, "celsius"),
        },
        response={"temperature": 18, "condition": "cloudy", "humidity": 72},
    )
    def conditions(self, params: dict) -> dict:
        # Replace with a real HTTP call in production.
        # BaseProxy.call() handles the HTTP plumbing when base_url is set.
        city = params["city"]
        return {"temperature": 18, "condition": "cloudy", "humidity": 72}

    @BaseProxy.endpoint(
        category="forecast",
        endpoint="daily",
        description="5-day daily forecast for a city.",
        params={
            "city*": (str, "London"),
            "days": (int, 5),
        },
        response=[{"date": "2024-01-01", "high": 20, "low": 12}],
    )
    def daily(self, params: dict) -> list:
        city = params["city"]
        return [{"date": f"2024-01-0{i}", "high": 18 + i, "low": 10 + i} for i in range(1, 6)]
```

Key conventions:
- `path` in `@ProxyRegistrator` is what users put in `activate_proxies`
- Parameters with `*` suffix are required; the second tuple element is the example value
- `response` is the example response used in docs and `auto_test()`

---

## Step 2: Configure the agent

Add a `proxy:` block to the agent config. With `exec_env: interpreter` (the default), LLLM builds a `ProxyManager`, an `AgentInterpreter`, and injects both tools before creating the `Agent`:

```yaml
# config.yaml
global:
  model_name: gpt-4o
  model_args:
    temperature: 0.1

agent_configs:
  - name: weather_analyst
    system_prompt: "You are a weather analyst. Use the Weather API to answer questions."
    proxy:
      activate_proxies: [weather]
      exec_env: interpreter       # default — can be omitted
      max_output_chars: 5000
      timeout: 60.0
```

Or in Python:

```python
config = {
    "global": {"model_name": "gpt-4o", "model_args": {"temperature": 0.1}},
    "agent_configs": [
        {
            "name": "weather_analyst",
            "system_prompt": "You are a weather analyst. Use the Weather API.",
            "proxy": {
                "activate_proxies": ["weather"],
                "exec_env": "interpreter",
                "max_output_chars": 5000,
            },
        }
    ],
}
```

At build time LLLM appends a block to the system prompt that explains `CALL_API`, `run_python`, state persistence, and truncation — the agent knows how to use these without extra prompt engineering on your part.

---

## Step 3: Run the tactic

```python
from lllm import Tactic
from lllm.logging import noop_store

class WeatherTactic(Tactic):
    name = "weather"
    agent_group = ["weather_analyst"]

    def call(self, task: str) -> str:
        agent = self.agents["weather_analyst"]
        agent.open("main")
        agent.receive(task)
        return agent.respond().content

tactic = WeatherTactic(config, log_store=noop_store())
print(tactic("What is the current weather in Tokyo and Paris?"))
```

The agent will typically:
1. Call `query_api_doc("weather")` to see full endpoint specs
2. Call `run_python` with code that calls `CALL_API("weather/conditions", {"city": "Tokyo"})`
3. Call `run_python` again (reusing variables) to process both cities and format the answer

---

## How the interpreter works

`AgentInterpreter` uses a persistent `namespace` dict passed to every `exec()` call:

```python
# Agent turn 1: fetch data
data_tokyo = CALL_API("weather/conditions", {"city": "Tokyo"})
data_paris = CALL_API("weather/conditions", {"city": "Paris"})
print(data_tokyo)
print(data_paris)
```

```python
# Agent turn 2: data_tokyo and data_paris are still in scope
comparison = f"Tokyo: {data_tokyo['temperature']}°C, Paris: {data_paris['temperature']}°C"
print(comparison)
```

This works because each agent instance has its own `AgentInterpreter` with its own namespace. Variables accumulate across calls like a live REPL session.

**Stdout capture** — output is collected from stdout only. The last expression is not auto-returned. Always use `print()`.

**Exception handling** — uncaught exceptions are caught and returned as formatted tracebacks, so the agent can read the error, fix the code, and retry without losing session state.

**Truncation** — output longer than `max_output_chars` is cut off and the `truncation_indicator` is appended (default: `"... (truncated)"`). The agent is told this in the injected prompt block.

**Timeout** — each `run_python` call runs in a daemon thread with a `timeout` (default 60s). If the thread doesn't finish in time, `TimeoutError` is raised.

---

## Global vs per-agent proxy config

Set defaults under `global:` and override per agent:

```yaml
global:
  model_name: gpt-4o
  proxy:
    activate_proxies: [fmp, fred]
    deploy_mode: false
    exec_env: interpreter

agent_configs:
  - name: fast_analyst
    # inherits global proxy config entirely

  - name: notebook_analyst
    proxy:
      exec_env: jupyter    # override: this agent uses JupyterSession
      # activate_proxies etc. inherited from global

  - name: crypto_analyst
    proxy:
      activate_proxies: [fmp]   # override: only fmp
      timeout: 30.0             # override: shorter timeout
```

Per-agent values deep-merge on top of global, field by field.

---

## query_api_doc — lazy endpoint discovery

Before using any endpoint, the agent calls `query_api_doc` with the proxy name:

```
query_api_doc("weather")
→ "## Weather API\n\n### conditions\n  city* (str): ...\n  units (str): ..."
```

This is injected as a tool with interrupt handling — the result is fed back to the agent automatically, just like any other tool call. The agent typically does this once per session.

---

## Full config reference

```yaml
proxy:
  activate_proxies: [fmp, fred]   # which proxies to load; empty = all registered
  deploy_mode: false               # passed to proxy instances (e.g. for rate limiting)
  cutoff_date: "2024-01-01"        # ISO date; proxies can use this to filter data
  exec_env: interpreter            # "interpreter" | "jupyter" | null
  max_output_chars: 5000           # truncate run_python stdout; 0 = no limit
  truncation_indicator: "... (truncated)"
  timeout: 60.0                    # seconds per run_python call; interpreter only
  prompt_template: null            # custom template string; null = auto-select
```

---

## Jupyter mode

Use `exec_env: jupyter` when you need:
- Notebook files (`.ipynb`) as output artifacts
- Matplotlib / Plotly visualizations written to the notebook
- Cell-level error recovery and reproducible audit trails

In Jupyter mode, only `query_api_doc` is injected as a tool. The agent writes
`<python_cell>` and `<markdown_cell>` XML tags in its response. Your tactic
extracts these and runs them in a `JupyterSession`:

```python
from lllm.sandbox.jupyter import JupyterSession

session = JupyterSession(
    name="analysis",
    dir="/tmp/notebooks",
    metadata={"proxy": {"activate_proxies": ["fmp"], "deploy_mode": False}},
)
session.init_session()   # injects CALL_API into the kernel namespace

# ... agent dialog loop ...
for tag, code in parsed["cells"]:
    if tag == "python_cell":
        output = session.run_cell(code)
    else:
        session.add_markdown_cell(code)
```

See the [Proxies & Sandbox reference](../core/proxy-and-sandbox.md) for a complete Jupyter mode example.

---

## When to use interpreter vs Jupyter

| | Interpreter | Jupyter |
|--|-------------|---------|
| Overhead | None (in-process exec) | Subprocess per kernel (~2-3s startup) |
| Parallel agents | Safe — isolated namespaces | Heavy — one subprocess per agent |
| Visualizations | Not available | Full matplotlib/plotly support |
| Output artifact | None | `.ipynb` notebook file |
| Audit trail | None | Cell-by-cell execution history |
| Best for | Data retrieval, computation, API orchestration | Exploratory analysis, reports with charts |

For most production use cases — API calls, data wrangling, multi-step computations — interpreter mode is the right choice.
