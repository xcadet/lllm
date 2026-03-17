# Project Structure

LLLM projects grow incrementally. You never need to restructure existing code — you add files alongside what you have. This page shows the recommended layout at each stage.

---

## Stage 1: Single script

A prototype or experiment. Everything is inline.

```
my_project/
└── main.py
```

```python
# main.py
from lllm import Tactic

agent = Tactic.quick("You are a helpful assistant.", model="gpt-4o")
agent.open("session")
agent.receive("Hello")
print(agent.respond().content)
```

No config needed. Just run it.

---

## Stage 2: Adding prompts

When your system prompts grow long or you want to version-control them separately, move them to `.md` files and add `lllm.toml`.

```
my_project/
├── lllm.toml
├── prompts/
│   └── assistant_system.md
└── main.py
```

```toml
# lllm.toml
[package]
name = "my_project"
version = "0.1.0"

[prompts]
paths = ["prompts/"]
```

```python
# main.py
from lllm import Tactic, load_prompt

prompt = load_prompt("assistant_system")
agent = Tactic.quick(prompt, model="gpt-4o")
agent.open("session")
agent.receive("Hello")
print(agent.respond().content)
```

LLLM auto-discovers `prompts/assistant_system.md` and registers it by its path-relative name.

---

## Stage 3: Multi-agent project

A full project with multiple agents, configs, and a custom tactic.

```
my_project/
├── lllm.toml
├── prompts/
│   ├── researcher_system.md
│   └── writer_system.md
├── configs/
│   └── research_writer.yaml
├── tactics/
│   └── research_writer.py
├── runs/               ← session checkpoints (auto-created)
└── main.py
```

```toml
# lllm.toml
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

```yaml
# configs/research_writer.yaml
agent_group_configs:
  researcher:
    model_name: gpt-4o
    system_prompt_path: researcher_system
    temperature: 0.3
  writer:
    model_name: gpt-4o
    system_prompt_path: writer_system
    temperature: 0.7
```

```python
# tactics/research_writer.py
from lllm import Tactic

class ResearchWriter(Tactic):
    name = "research_writer"
    agent_group = ["researcher", "writer"]

    def call(self, topic: str, **kwargs) -> str:
        researcher = self.agents["researcher"]
        writer = self.agents["writer"]

        researcher.open("research", prompt_args={"topic": topic})
        findings = researcher.respond()

        writer.open("draft", prompt_args={"findings": findings.content})
        return writer.respond().content
```

```python
# main.py
from lllm import build_tactic, load_config

config = load_config("research_writer")
tactic = build_tactic(config, ckpt_dir="./runs")
result = tactic("The future of AI")
print(result)
```

---

## Stage 4: Multi-package project

When you want to share tactics or prompts across projects, split into packages. Each package has its own `lllm.toml`.

```
workspace/
├── shared_lib/
│   ├── lllm.toml
│   └── prompts/
│       └── common_system.md
└── my_project/
    ├── lllm.toml       ← depends on shared_lib
    ├── prompts/
    └── main.py
```

```toml
# my_project/lllm.toml
[package]
name = "my_project"
version = "0.1.0"

[prompts]
paths = ["prompts/"]

[dependencies]
packages = ["../shared_lib"]
```

Resources from `shared_lib` are available under the `shared_lib` namespace:

```python
from lllm import load_prompt

# local prompt
prompt = load_prompt("my_prompt")

# from dependency
shared_prompt = load_prompt("shared_lib.prompts:common_system")
```

See [Packages](../core/packages.md) for full details on namespacing, aliasing, and cycle detection.

---

## Naming Conventions

| Resource type | Location | Naming |
|---|---|---|
| System prompts | `prompts/<agent>_system.md` | `<agent>_system` |
| User prompt templates | `prompts/<agent>_user.md` | `<agent>_user` |
| Agent configs | `configs/<tactic_name>.yaml` | `<tactic_name>` |
| Tactic classes | `tactics/<tactic_name>.py` | class `<TacticName>` |
| Proxy classes | `proxies/<service>_proxy.py` | class `<Service>Proxy` |

---

## Session & Log Output

```
runs/
├── sessions/           ← checkpoint files per tactic run
│   └── 20250316_142301_a3f7b2c1.json
└── logs/               ← if using local_store()
    └── ...
```

The `ckpt_dir` argument to `build_tactic()` (or the tactic constructor) controls where checkpoints land. Pass `ckpt_dir=None` to disable checkpointing.

---

## Configuration Tips

**Environment variables override TOML:**

```bash
export LLLM_CONFIG=/path/to/custom/lllm.toml
```

**Multiple environments:** keep separate TOML files and switch with `LLLM_CONFIG`:

```bash
LLLM_CONFIG=lllm.prod.toml python main.py
```

**Validate your config before running:**

```python
from lllm import load_config
config = load_config("my_tactic")
print(config)  # inspect the merged config dict
```
