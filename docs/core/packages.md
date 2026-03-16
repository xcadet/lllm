# Packages

LLLM is Pythonic, while LLLM itself is self-contained, and you can just use it as a library and organize your own code as you want. However, it is recommended to separate the LLLM resources (prompts, proxies, configs, and tactics) from the upper-level system by encapsulating them into a package for better organization and reusability.

An LLLM package is structured as follows:

```
package_name/
  ├── prompts/        # the prompts, for the agents to call
  ├── proxies/        # the proxies, for proxy-based tool-calling
  ├── configs/        # the configs for the agents (YAML files)
  ├── tactics/        # the tactics, programs that wire agents and prompts together
  ├── lllm.toml       # package metadata and dependency declarations
```

An example structure of an LLLM agentic system:

```
project_name/
├── lllm.toml         # root package — LLLM finds this automatically
├── lllm_packages/
  ├── my_package1/
  ├── my_package2/
├── ... (application code, data, etc.)
```

Conceptually, LLLM maintains a registry of prompts, proxies, configs, and tactics, loaded on demand through the `lllm.toml` file. All resources are indexed by URLs of the form `<package>.<section>:<resource_path>`. Tactics are the top-level building blocks — they find agent configs by key, prompts from the prompt registry, and proxy-based tools from the proxy registry.


## Runtime Initialization

By default, when LLLM is imported, it looks for `lllm.toml` starting from the current working directory and searching upward. If found, it loads the package tree into the default runtime. If no `lllm.toml` is found, the default runtime is initialized empty (useful for fast mode and testing).

```python
from lllm import load_prompt  # default runtime already populated from project root

# Explicit load / replace default runtime
from lllm import load_runtime
load_runtime("path/to/custom.toml")

# Named runtimes for parallel experiments
load_runtime("experiment_a/lllm.toml", name="exp_a")
load_runtime("experiment_b/lllm.toml", name="exp_b")

from lllm import get_runtime
rt_a = get_runtime("exp_a")
rt_b = get_runtime("exp_b")
```


## Resources

LLLM has four built-in resource types: prompts, proxies, configs, and tactics. You can also define custom resource types via custom TOML sections.

Every resource is internally wrapped in a `ResourceNode` object, which manages the qualified key, namespace, lazy loading, and metadata. `ResourceNode` is a **wrapper**, not a base class — the existing classes (Prompt, Tactic, BaseProxy) do not inherit from it.

For eager resources (prompts, tactics discovered at import time), the value is set immediately. For lazy resources (config YAML files, custom assets), the `ResourceNode` holds a loader callable and the file is only read on first access, then cached.


## lllm.toml Format

An `lllm.toml` has six official sections: `[package]`, `[prompts]`, `[proxies]`, `[configs]`, `[tactics]`, and `[dependencies]`. Custom sections like `[assets]` are also supported.

- **[package]**: Package identity — name, version, description. All resources declared in this TOML are namespaced under this package name.
- **[prompts]**: Paths to prompt folders. Defaults to `prompts/` if omitted. Empty if neither the section nor the subfolder exists.
- **[proxies]**: Paths to proxy folders. Defaults to `proxies/`.
- **[configs]**: Paths to config folders (YAML files, loaded lazily). Defaults to `configs/`.
- **[tactics]**: Paths to tactic folders. Defaults to `tactics/`.
- **[dependencies]**: Paths to other packages. Dependencies are loaded into their own namespace only. To re-export a dependency's resources into the current package namespace, list their paths explicitly in the relevant resource section.


## Resource Indexing

Resources are indexed by URLs with the format `<package_name>.<section_name>:<resource_path>`. There is always exactly one `:` separator.

The `resource_path` is built from the folder structure relative to the declared path root: `<subfolder>/.../<filename>/<object_name>`. Root folders are stripped — multiple `paths` entries merge into a flat namespace.

When a key collision occurs during discovery (two paths producing the same resource key), LLLM logs a warning. The later registration overwrites the earlier one. Use the `under` keyword to disambiguate.

### Example

Given `[prompts] paths = [".../prompts_1", ".../prompts_2"]` under package `my_pkg`:

```
prompts_1/
├── greet.py          # contains: hello, goodbye
├── sub/
    ├── deep.py       # contains: analyzer

prompts_2/
├── tools.py          # contains: searcher
```

The resulting URLs are:

- `my_pkg.prompts:greet/hello`
- `my_pkg.prompts:greet/goodbye`
- `my_pkg.prompts:sub/deep/analyzer`
- `my_pkg.prompts:tools/searcher`

### Convenience Access

Full URL via `load_resource` (always requires section):

```python
load_resource("my_pkg.prompts:greet/hello")
load_resource("prompts:greet/hello")          # section-only → default package
```

Typed convenience functions (section inferred):

```python
load_prompt("my_pkg:greet/hello")             # package-qualified
load_prompt("greet/hello")                     # bare → default package namespace
```


## Resource Loading

### Dependency-Only Loading

```toml
[package]
name = "my_system"

[dependencies]
packages = ["./packages/child_pkg", "../shared/shared_pkg"]
```

Each dependency's resources live in their own namespace:

```python
load_prompt("child_pkg:greet/hello")
load_prompt("shared_pkg:tools/searcher")
```

No resources exist under `my_system` — dependencies are isolated unless re-exported.


### Re-Exporting Into the Current Namespace

List paths explicitly in resource sections to include them in the current package's namespace:

```toml
[package]
name = "my_system"

[prompts]
paths = ["./packages/child_pkg/prompts", "../shared/shared_pkg/prompts"]

[dependencies]
packages = ["./packages/child_pkg", "../shared/shared_pkg"]
```

Now resources are accessible via both namespaces:

```python
load_prompt("greet/hello")                    # via my_system (default)
load_prompt("child_pkg:greet/hello")          # via dependency namespace
```


## Alias Loading

Two mechanisms address name collisions:

- **`as`** on dependencies — creates an additional alias. The original name still works.
- **`under`** on resource paths — adds a virtual root folder prefix within the importing package's namespace.

Both can be specified as inline strings or standard TOML inline tables — the two forms are exactly equivalent:

```toml
# String keyword form
packages = ["./packages/child_pkg as cp"]
paths = ["./some/path under vendor"]

# TOML inline table form
packages = [{path = "./packages/child_pkg", alias = "cp"}]
paths = [{path = "./some/path", prefix = "vendor"}]

# Table form also accepts the keyword names
packages = [{path = "./packages/child_pkg", as = "cp"}]
paths = [{path = "./some/path", under = "vendor"}]
```

### Example

```toml
[package]
name = "my_system"

[tactics]
paths = ["./pkg1/tactics under v1", "./pkg2/tactics under v2"]

[prompts]
paths = ["./pkg1/prompts", "./pkg2/prompts under vendor"]

[dependencies]
packages = ["./pkg1 as p1", "./pkg2 as p2"]
```

Access patterns:

```python
# Tactics from pkg1, re-exported into my_system with v1 prefix:
load_tactic("v1/my_tactic")                 # via default namespace
load_tactic("my_system:v1/my_tactic")        # explicit

# Same tactic via pkg1's own namespace (no prefix):
load_tactic("p1:my_tactic")                  # via alias
load_tactic("pkg1:my_tactic")                # via original name (still works)

# Prompts from pkg2 with vendor prefix:
load_prompt("vendor/my_prompt")              # via default namespace
load_prompt("p2:my_prompt")                  # via alias (no prefix)
```

Note: `under` modifies how resources appear in the **importing** package's namespace, not in the source package's own namespace.


## Custom Sections

Beyond the four built-in sections, you can define any custom section in `lllm.toml` to package arbitrary files — images, ML model weights, JSON schemas, data files, or anything else your system needs.

### How It Works

Custom sections follow the same `paths` / `under` mechanics as built-in sections. During discovery, LLLM walks the declared folders and registers every file as a lazy `ResourceNode`. Files are **not read until first access** — a package with 500MB of model weights costs nothing at import time.

File loading behavior depends on extension:

| Extension | Loaded as |
| --- | --- |
| `.json` | Parsed via `json.load` → `dict` / `list` |
| `.yaml`, `.yml` | Parsed via `yaml.safe_load` → `dict` / `list` |
| `.toml` | Parsed via `tomllib.load` → `dict` |
| Everything else | Raw `bytes` via `Path.read_bytes()` |

Resource keys **include the file extension** (unlike Python-based sections where `.py` is stripped), because the extension is part of the file identity — `logo.png` and `logo.svg` are different resources.

Any `.py` files in custom section folders are also scanned for Python-defined resources (Prompt, Tactic, BaseProxy subclasses), so you can mix code and data in the same section.

### Declaring Custom Sections

```toml
[package]
name = "my_toolkit"

[assets]
paths = ["assets"]

[models]
paths = ["models"]

[schemas]
paths = ["schemas"]
```

With this directory structure:

```
my_toolkit/
├── lllm.toml
├── assets/
│   ├── logo.png
│   ├── banner.svg
│   └── templates/
│       └── email.html
├── models/
│   └── classifier.pt
└── schemas/
    └── api_spec.json
```

### Accessing Custom Resources

Use `load_resource` with `"pkg.section:path"` or `"section:path"` (section-only uses default package):

```python
from lllm import load_resource

# Full URL
logo_bytes = load_resource("my_toolkit.assets:logo.png")           # → bytes
api_spec = load_resource("my_toolkit.schemas:api_spec.json")       # → dict (parsed)

# Section-only (if my_toolkit is the default package)
logo_bytes = load_resource("assets:logo.png")
html = load_resource("assets:templates/email.html")                # → bytes

# Nested paths work naturally
weights = load_resource("models:classifier.pt")                    # → bytes
```

### Getting the File Path Directly

For large files or custom formats where the default loader isn't appropriate (e.g., loading a PyTorch model with `torch.load`), access the `ResourceNode` directly to get the file path:

```python
from lllm import get_default_runtime

runtime = get_default_runtime()
node = runtime.get_node("my_toolkit.models:classifier.pt")

# The absolute file path is stored in metadata
file_path = node.metadata["file_path"]

# Use your own loader
import torch
model = torch.load(file_path)
```

### Custom Sections with `under` Prefix

The `under` keyword works the same way as for built-in sections:

```toml
[assets]
paths = [
    "./icons under ui",
    "./photos under content",
]
```

```python
load_resource("assets:ui/check.svg")
load_resource("assets:content/hero.jpg")
```

### Example: ML Pipeline Package

```toml
[package]
name = "sentiment_analyzer"

[prompts]
paths = ["prompts"]

[configs]
paths = ["configs"]

[models]
paths = ["models"]

[assets]
paths = ["assets"]
```

```
sentiment_analyzer/
├── lllm.toml
├── prompts/
│   └── classify.py           # Prompt objects
├── configs/
│   └── default.yaml          # agent config
├── models/
│   ├── tokenizer.json        # parsed as dict automatically
│   └── weights.bin           # loaded as bytes
└── assets/
    └── label_map.json        # parsed as dict automatically
```

```python
from lllm import load_prompt, load_config, load_resource, resolve_config, get_default_runtime

# Typed loaders for built-in sections
prompt = load_prompt("sentiment_analyzer:classify/system")
config = resolve_config("default")

# Custom sections via load_resource
label_map = load_resource("models:label_map.json")   # → {"0": "negative", "1": "positive"}
tokenizer = load_resource("models:tokenizer.json")   # → dict

# Large binary — get path, load with custom code
node = get_default_runtime().get_node("sentiment_analyzer.models:weights.bin")
weights_path = node.metadata["file_path"]
# model = my_framework.load(weights_path)
```