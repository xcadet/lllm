"""
Proxy interpreter example — state-persistent Python tool use.

Demonstrates:
  - Defining an inline proxy with @ProxyRegistrator + @BaseProxy.endpoint
  - Configuring exec_env: interpreter in tactic config
  - Agent using run_python with CALL_API for multi-step data analysis
  - State persistence: variables from one run_python call available in the next
  - query_api_doc for on-demand endpoint documentation

No external API keys are required for the proxy itself; only an LLM key
(OPENAI_API_KEY or ANTHROPIC_API_KEY) is needed to run the agent.

Usage:
    python examples/advanced/proxy_interpreter.py

Prerequisites:
    export OPENAI_API_KEY=sk-...   # or ANTHROPIC_API_KEY, etc.
"""
import sys
import os

# Allow running from the repo root without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from _api_key import MODEL  # noqa: E402  (relative to this folder)

from lllm import Tactic
from lllm.logging import noop_store
from lllm.proxies import BaseProxy, ProxyRegistrator
from lllm.core.runtime import Runtime


# ---------------------------------------------------------------------------
# 1. Define an inline proxy that uses pure in-process computation
#    (no external HTTP calls — the proxy is the API)
# ---------------------------------------------------------------------------

# A dedicated runtime keeps this example self-contained and avoids
# polluting the global default runtime with example-only proxies.
_rt = Runtime()


@ProxyRegistrator(
    path="stats",
    name="Statistics API",
    description=(
        "Generates synthetic datasets and computes statistical summaries. "
        "Useful for demonstrating multi-step data analysis."
    ),
    runtime=_rt,
)
class StatsProxy(BaseProxy):

    @BaseProxy.endpoint(
        category="data",
        endpoint="generate",
        description=(
            "Generate a list of N random integers in the range [low, high]. "
            "Pass a seed for reproducible results."
        ),
        params={
            "n*": (int, 20),
            "low": (int, 0),
            "high": (int, 100),
            "seed": (int, 42),
        },
        response={"data": [42, 7, 88, 15, 63]},
    )
    def generate(self, params: dict) -> dict:
        import random
        n = params.get("n", 20)
        low = params.get("low", 0)
        high = params.get("high", 100)
        seed = params.get("seed")
        rng = random.Random(seed)
        return {"data": [rng.randint(low, high) for _ in range(n)]}

    @BaseProxy.endpoint(
        category="data",
        endpoint="fibonacci",
        description="Return the first N Fibonacci numbers as a list.",
        params={"n*": (int, 10)},
        response={"sequence": [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]},
    )
    def fibonacci(self, params: dict) -> dict:
        n = params.get("n", 10)
        seq: list = []
        a, b = 0, 1
        for _ in range(n):
            seq.append(a)
            a, b = b, a + b
        return {"sequence": seq}

    @BaseProxy.endpoint(
        category="analysis",
        endpoint="summarize",
        description="Compute count, mean, min, max, and std-dev for a list of numbers.",
        params={"data*": (list, [1, 2, 3, 4, 5])},
        response={
            "count": 5,
            "mean": 3.0,
            "min": 1,
            "max": 5,
            "std": 1.41,
        },
    )
    def summarize(self, params: dict) -> dict:
        import math
        data = params.get("data", [])
        if not data:
            return {"count": 0, "mean": None, "min": None, "max": None, "std": None}
        n = len(data)
        mean = sum(data) / n
        variance = sum((x - mean) ** 2 for x in data) / n
        return {
            "count": n,
            "mean": round(mean, 4),
            "min": min(data),
            "max": max(data),
            "std": round(math.sqrt(variance), 4),
        }


# ---------------------------------------------------------------------------
# 2. Build a tactic that uses exec_env: interpreter
# ---------------------------------------------------------------------------

class DataAnalysisTactic(Tactic):
    """Single-agent tactic that answers data questions using the Stats API."""

    name = "data_analysis"
    agent_group = ["analyst"]

    def call(self, task: str) -> str:
        agent = self.agents["analyst"]
        agent.open("main")
        agent.receive(task)
        return agent.respond().content


config = {
    "global": {
        "model_name": MODEL,
        "model_args": {"temperature": 0.1},
        "proxy": {
            "activate_proxies": ["stats"],
            "exec_env": "interpreter",     # agent gets run_python + query_api_doc
            "max_output_chars": 3000,
            "timeout": 30.0,
        },
    },
    "agent_configs": [
        {
            "name": "analyst",
            "system_prompt": (
                "You are a data analyst with access to a Statistics API. "
                "Use run_python with CALL_API to fetch and process data. "
                "Call query_api_doc('stats') if you need endpoint details. "
                "Always print your final answer clearly."
            ),
        }
    ],
}

tactic = DataAnalysisTactic(config, log_store=noop_store(), runtime=_rt)


# ---------------------------------------------------------------------------
# 3. Run example tasks
# ---------------------------------------------------------------------------

def run(task: str) -> None:
    print(f"Task: {task}")
    print("-" * 60)
    result = tactic(task)
    print(result)
    print()


# Task 1: single-step — generate and summarize in one prompt
run(
    "Generate 20 random integers between 0 and 50 with seed=42, "
    "then compute and report their mean, min, max, and standard deviation."
)

# Task 2: multi-step — demonstrates state persistence across run_python calls
#   The agent is expected to:
#     call 1 — fetch the Fibonacci sequence
#     call 2 — compute the ratio of successive terms (variables persist)
run(
    "Fetch the first 15 Fibonacci numbers. "
    "Then, in a separate run_python call, compute the ratio of each term "
    "to the previous one and print the last five ratios. "
    "(This demonstrates that variables from the first call are still available.)"
)
