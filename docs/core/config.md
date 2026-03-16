# Configuration & Discovery

LLLM favors composition over hard-coded imports. The `lllm.toml` manifest plus YAML config files allow an entire system to be wired together without editing Python entry points.


## lllm.toml — Package Discovery

`lllm.toml` drives resource discovery. Place it at the project root or point to it via `$LLLM_CONFIG`. The loader searches parent directories recursively, so you can run tools from subdirectories without losing context.

```toml
[package]
name = "my_system"
version = "0.1.0"

[prompts]
paths = ["prompts/"]

[configs]
paths = ["configs/"]

[tactics]
paths = ["tactics/"]

[dependencies]
packages = ["./packages/shared_lib"]
```

See the [Packages](packages.md) doc for full details on sections, namespacing, aliasing, and dependency loading.


## Environment Variables

| Variable | Purpose |
| --- | --- |
| `LLLM_CONFIG` | Absolute path to a config file or folder; overrides auto-detection. |


## Agent Configuration (YAML)

Agent config files live in the `configs/` section and define how agents are constructed. They are loaded lazily — the YAML file is only read when `load_config()` or `resolve_config()` is called.

### Structure

```yaml
base: ...              # optional — inherit from another config (no .yaml suffix)

global:                # default settings merged into every agent
  model_name: gpt-4o
  api_type: completion
  model_args:
    temperature: 0.1
  max_exception_retry: 3
  max_interrupt_steps: 5
  max_llm_recall: 3
  extra_settings: {}

agent_configs:         # list of per-agent configs
  - name: analyzer
    system_prompt_path: analytica/analyzer_system
    model_args:
      max_completion_tokens: 20000

  - name: synthesizer
    model_name: gpt-4o-mini          # overrides global
    system_prompt: "You are a synthesizer. Combine the analyses into a coherent report."
    model_args:
      temperature: 0.3               # overrides global
```

### Per-Agent Fields

| Field | Required | Description |
| --- | --- | --- |
| `name` | Yes | Agent identifier — must match an entry in the tactic's `agent_group`. |
| `model_name` | Yes (or from global) | Model identifier (e.g. `gpt-4o`, `o4-mini-2025-04-16`). |
| `system_prompt` | One of these | Inline system prompt string. Creates a `Prompt` object directly. |
| `system_prompt_path` | required | Path to a registered prompt in the runtime (e.g. `analytica/system`). |
| `api_type` | No | `"completion"` (default) or `"response"` for OpenAI Responses API. |
| `model_args` | No | Dict of model parameters (temperature, max_tokens, etc.). Merged with global. |
| `max_exception_retry` | No | Max retries on parse/validation errors. Default: 3. |
| `max_interrupt_steps` | No | Max consecutive tool-call interrupts. Default: 5. |
| `max_llm_recall` | No | Max retries on LLM API errors. Default: 0. |
| `extra_settings` | No | Reserved for advanced usage (context managers, etc.). |

Any unrecognized keys in a per-agent config are treated as additional `model_args`.

### Global Merge

The `global` section provides defaults for all agents. Per-agent values override global values. For `model_args` specifically, the dicts are **merged** (not replaced), so you can set `temperature` globally and override only `max_tokens` per agent.

```yaml
global:
  model_name: gpt-4o
  model_args:
    temperature: 0.1

agent_configs:
  - name: creative_writer
    model_args:
      temperature: 0.9        # overrides global
      max_tokens: 4000         # added to global model_args
    system_prompt: "You are a creative writer."
```

Result: `creative_writer` gets `model_name: gpt-4o`, `model_args: {temperature: 0.9, max_tokens: 4000}`.


### Inheritance via `base`

Configs can inherit from other configs using the `base` key. The value is the config name (relative path within the configs folder, no `.yaml` suffix). Inheritance is recursive and uses deep merge — dict values merge, lists and scalars replace.

```
configs/
  base.yaml
  experiments/
    ablation.yaml
    full.yaml
```

```yaml
# base.yaml
global:
  model_name: gpt-4o
  model_args:
    temperature: 0.1
agent_configs:
  - name: analyzer
    system_prompt_path: research/system
```

```yaml
# experiments/ablation.yaml
base: base                      # inherits from base.yaml
global:
  model_args:
    max_tokens: 500             # added to base's model_args
agent_configs:                  # replaces base's list (list = replace, not merge)
  - name: analyzer
    system_prompt_path: research/system_no_cot
```

```yaml
# experiments/full.yaml
base: experiments/ablation      # chain: full → ablation → base
global:
  model_name: o4-mini-2025-04-16   # overrides base's gpt-4o
```

Resolve the chain:

```python
from lllm import resolve_config

config = resolve_config("experiments/full")
# config["global"]["model_name"] == "o4-mini-2025-04-16"
# config["global"]["model_args"]["temperature"] == 0.1 (from base)
# config["global"]["model_args"]["max_tokens"] == 500 (from ablation)
```

Circular inheritance is detected and raises `ValueError`.


## How Configs Connect to Tactics

A `Tactic` reads `agent_configs` from the config dict during construction:

```python
from lllm import build_tactic, resolve_config

config = resolve_config("experiments/full")
tactic = build_tactic(config, ckpt_dir="./runs", name="analytica")
result = tactic("Analyze this paper")
```

Internally, `parse_agent_configs(config, agent_group, tactic_name)` extracts the `global` section, merges it into each agent entry, and produces an `AgentSpec` per agent. At call time, `AgentSpec.build()` constructs the live `Agent` — resolving `system_prompt_path` from the runtime or using the inline `system_prompt`.

```python
from lllm import AgentSpec, parse_agent_configs

# Manual parsing (usually done by Tactic.__init__ automatically)
specs = parse_agent_configs(config, ["analyzer", "synthesizer"], "my_tactic")
agent = specs["analyzer"].build(runtime, invoker, log_base)
```


## Auto-Discovery Workflow

When `lllm` is imported (or `load_runtime()` is called):

1. Find the nearest `lllm.toml` (via `$LLLM_CONFIG` or upward directory search).
2. Parse `[package]` metadata, register the package.
3. Load `[dependencies]` recursively (depth-first, with cycle detection).
4. For each resource section (`[prompts]`, `[proxies]`, `[configs]`, `[tactics]`, custom sections):
   - Resolve paths (with `under` prefix if specified).
   - For Python sections: recursively walk folders, import `.py` files, scan for typed objects (`Prompt`, `BaseProxy` subclasses, `Tactic` subclasses).
   - For configs: recursively walk folders for `.yaml`/`.yml` files, register as lazy `ResourceNode`s.
5. For dependencies with `as` aliases: re-register all resources under the alias namespace.

Because registration happens at import time for Python resources, adding a new prompt file to the folder makes it available without touching central registries.


## Managing Dependency Configs

When your package depends on other packages (A, B, C), each with their own configs, you need a strategy for keeping configuration coherent without invisible coupling.

### Principle

**Each package is responsible for configuring its own dependencies.** When you import package A, you trust that A's `default.yaml` handles everything A needs (including A's own dependencies). You only override the parts that matter to your use case.

Cross-package `base` references (e.g., `base: "A:default"`) are **not allowed** in normal config files — a package's config should be self-contained. The one exception is the explicit vendoring pattern described below.

### The Assembly Config Pattern

Your top-level config is the single point of control. It assembles agent configs from all sources — your own agents plus agents that use prompts from dependencies:

```yaml
# configs/default.yaml
tactic_type: my_research_system

global:
  model_name: gpt-4o
  model_args:
    temperature: 0.1

agent_configs:
  # Your own agent
  - name: orchestrator
    system_prompt_path: my_pkg:orchestrator/system

  # Agent using prompts from package A
  - name: analyzer
    system_prompt_path: A:analysis/system
    model_args:
      max_completion_tokens: 20000

  # Agent using prompts from package B  
  - name: searcher
    system_prompt_path: B:search/system
    model_name: gpt-4o-mini
```

Prompt *references* point to dependencies (that's fine — it's like importing a function). But *configuration decisions* (model, temperature, retries) are owned by you.

### Config Vendoring for Sub-Tactics

When you compose dependency tactics as sub-tactics, their configs need to be available too. Use `vendor_config` to pull a dependency's config, apply your overrides, and register the result as your own:

```python
from lllm import vendor_config, get_default_runtime

# Pull package A's config and pin to your model choices
cfg = vendor_config("A:default", {
    "global": {
        "model_name": "gpt-4o",
        "model_args": {"temperature": 0.05},
    },
})

# Register as your own vendored config
runtime = get_default_runtime()
runtime.register_config("vendor/A", cfg, namespace="my_pkg.configs")
```

Or equivalently, write a YAML file that uses `base` to inherit from the dependency:

```yaml
# configs/vendor/A.yaml
base: "A:default"
global:
  model_name: gpt-4o
  model_args:
    temperature: 0.05
```

Both approaches produce the same result: a fully materialized config with your overrides applied on top.

### Recommended Directory Structure

```
my_system/
├── lllm.toml
├── configs/
│   ├── default.yaml            # main assembly config
│   ├── experiments/
│   │   ├── fast.yaml           # base: default → swap to mini models
│   │   └── ablation.yaml       # base: default → swap prompts
│   └── vendor/                 # frozen/overridden dependency configs
│       ├── A.yaml              # base: "A:default" + overrides
│       └── B.yaml              # base: "B:default" + overrides
├── prompts/
├── tactics/
└── ...
```

### What NOT To Do

Do not mirror the dependency tree in your config directory:

```
# ❌ Don't do this
configs/
  packages/
    A/
      packages/
        X/         # A's dependency — not your problem
```

If A depends on X, A's config handles X. You only configure A.

### `vendor_config` API

```python
from lllm import vendor_config

# Basic: resolve and return
cfg = vendor_config("A:default")

# With overrides (deep-merged)
cfg = vendor_config("A:default", {
    "global": {"model_name": "gpt-4o-mini"},
})

# Save to disk for version control
import yaml
with open("configs/vendor/A.yaml", "w") as f:
    yaml.dump(cfg, f)
```

`vendor_config` resolves the full `base` chain first, then applies your overrides via deep merge. The result has no `base` key — it's a standalone config.