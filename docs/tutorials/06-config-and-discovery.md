# Lesson 6 — Configuration and Auto-Discovery

As a project grows, hard-coded prompts and inline configs become hard to manage. LLLM's config system lets you declare resources in files and have them discovered automatically at startup.

---

## The `lllm.toml` File

Copy the example template to your project root:

```bash
cp lllm.toml.example lllm.toml
```

A minimal config:

```toml
[package]
name = "my_project"
version = "0.1.0"

[prompts]
paths = ["prompts/"]

[configs]
paths = ["configs/"]

[tactics]
paths = ["tactics/"]
```

LLLM scans the listed directories at startup. Any `Prompt` objects found in `.py` files are registered; any `.yaml`/`.yml` files in `configs/` are registered as config resources.

---

## Project Layout

```
my_project/
├── lllm.toml
├── prompts/
│   ├── greeter.py          # contains Prompt objects
│   └── analyst/
│       └── system.py
├── configs/
│   └── default.yaml        # tactic config
└── tactics/
    └── analyzer.py         # contains Tactic subclasses
```

---

## Auto-Discovered Prompts

```python
# prompts/greeter.py
from lllm import Prompt

greeter_system = Prompt(
    path="greeter/system",
    prompt="You are {name}, a friendly assistant.",
)
```

After auto-discovery, load this prompt anywhere:

```python
from lllm import load_prompt

p = load_prompt("greeter/system")
```

The fully-qualified key (including the package namespace) is also accepted:

```python
p = load_prompt("my_project:greeter/system")
```

---

## Agent Config YAML

Define agents in a YAML file instead of inline Python dicts:

```yaml
# configs/default.yaml
tactic_type: analyzer

global:
  model_name: gpt-4o
  model_args:
    temperature: 0.1

agent_configs:
  - name: extractor
    system_prompt_path: analyst/system      # resolves to the registered Prompt
    model_args:
      max_completion_tokens: 4000
  - name: synthesizer
    system_prompt: "You are a concise writer."   # inline system prompt
```

Load and resolve the config at runtime:

```python
from lllm import resolve_config, build_tactic

config = resolve_config("default")
tactic = build_tactic(config, name="analyzer")
```

---

## Config Inheritance with `base`

```yaml
# configs/base.yaml
global:
  model_name: gpt-4o
  model_args:
    temperature: 0.1
    seed: 42

agent_configs:
  - name: writer
    system_prompt: "You are a technical writer."
```

```yaml
# configs/fast.yaml
base: base    # inherits from base.yaml

global:
  model_name: gpt-4o-mini   # overrides model; other fields are kept
```

`resolve_config("fast")` deep-merges `fast.yaml` on top of `base.yaml`. Dict fields are merged recursively; scalars are replaced.

---

## Vendoring a Dependency's Config

When your project depends on another LLLM package, you can vendor its config and apply overrides:

```python
from lllm import vendor_config

cfg = vendor_config("other_pkg:default", overrides={
    "global": {"model_name": "claude-opus-4-6"},
})
```

This materialises the dependency's config into a standalone dict that no longer requires the dependency to be present.

---

## Package Dependencies

Declare LLLM package dependencies in `lllm.toml`:

```toml
[dependencies]
packages = [
    "./shared_prompts as shared",    # load ./shared_prompts, alias its namespace to "shared"
    "../another_pkg",
]
```

Dependent packages are loaded recursively with cycle detection. After loading, their resources are accessible under their package name (or alias):

```python
p = load_prompt("shared:common/system")
```

---

## Named Runtimes

For running parallel experiments without cross-contamination:

```python
from lllm import load_runtime, get_runtime

# Load a dedicated runtime from a specific config
load_runtime("experiment_1", config_path="./configs/exp1/lllm.toml")
load_runtime("experiment_2", config_path="./configs/exp2/lllm.toml")

rt1 = get_runtime("experiment_1")
rt2 = get_runtime("experiment_2")
```

Each named runtime has its own registry. Tactics built against `rt1` only see resources from `rt1`.

---

## Convenience Loaders

```python
from lllm import load_prompt, load_tactic, load_proxy, load_config, load_resource

p   = load_prompt("my_prompt")
t   = load_tactic("my_tactic")
cfg = load_config("default")
```

These all delegate to `get_default_runtime()` so they always see the auto-discovered resources.

---

## Virtual Folder Prefixes (`under`)

When you want resources from a folder to appear under a different path in the registry:

```toml
[prompts]
paths = [
    { path = "prompts/v2/", under = "v2" }
]
```

A file at `prompts/v2/greeter.py` with `path="greeter/system"` will be registered as `v2/greeter/system`.

---

## What Gets Discovered

| File type | Registered as |
|---|---|
| `.py` with `Prompt` instances | prompts |
| `.py` with `BaseProxy` subclasses | proxies |
| `.py` with `Tactic` subclasses | tactics |
| `.yaml` / `.yml` in `configs/` | configs |
| Any other file in a custom section | raw bytes or parsed dict |

---

## Summary

| Task | How |
|---|---|
| Auto-register prompts | Put `Prompt` objects in `.py` files in a scanned folder |
| Define agents via YAML | `agent_configs:` list in a `.yaml` config file |
| Config inheritance | `base: parent_config` in YAML |
| Load a config | `resolve_config("name")` |
| Load a prompt | `load_prompt("path")` |
| Package dependencies | `[dependencies] packages = [...]` in `lllm.toml` |
| Named runtimes | `load_runtime("name", ...)` |

**Next:** [Lesson 7 — Logging and Cost Tracking](07-logging.md)
