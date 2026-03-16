# Proxies & Sandbox

LLLM treats tool access as a first-class capability. Proxies standardize how agents reach external APIs, while the sandbox module enables stateful notebook or browser-style execution.

## BaseProxy & Endpoint Registration

`lllm/proxies/base.py` defines `BaseProxy`, a reflection-based registry for HTTP endpoints. Endpoints are declared via decorators:

```python
from lllm.proxies import BaseProxy, ProxyRegistrator

@ProxyRegistrator(path="finance/fmp", name="Financial Modeling Prep", description="Market data API")
class FMPProxy(BaseProxy):
    base_url = "https://financialmodelingprep.com/api/v3"
    api_key_name = "apikey"

    @BaseProxy.endpoint(
        category="search",
        endpoint="search-symbol",
        description="Search tickers",
        params={"query*": (str, "AAPL"), "limit": (int, 10)},
        response=[{"symbol": "AAPL", "name": "Apple"}],
    )
    def search_symbol(self, params):
        return params
```

`@ProxyRegistrator` registers the class into the runtime at decoration time (import time). The `path` argument becomes the resource key — e.g., `"finance/fmp"`. This key is used by `Proxy()` for dispatch and by `activate_proxies` for filtering.

`@BaseProxy.endpoint` is metadata-only — it records category, params, response schema, etc. on the method for documentation and auto-testing. Helpers like `endpoint_directory()`, `api_directory()`, and `auto_test()` use this metadata.


## Three Ways Proxies Enter the Registry

### 1. `@ProxyRegistrator` at Import Time

The primary mechanism. When a module containing a decorated class is imported, the class is registered immediately:

```python
@ProxyRegistrator(path="wa", name="Wolfram Alpha API", description="...")
class WAProxy(BaseProxy):
    ...
# WAProxy is now registered under key "wa" in the default runtime
```

### 2. Discovery via `lllm.toml`

List proxy folders in the `[proxies]` section:

```toml
[package]
name = "my_system"

[proxies]
paths = ["proxies"]
```

Discovery recursively walks the folder, imports every `.py` file (triggering any `@ProxyRegistrator` decorators), and also scans for `BaseProxy` subclasses directly. A proxy discovered under package `my_system` is available as both:
- `"wa"` (bare key, from `@ProxyRegistrator`)
- `"my_system.proxies:wa"` (namespaced key, from discovery)

### 3. `load_builtin_proxies()` for Manual Use

LLLM ships with built-in proxies (financial data, search, Wolfram Alpha, etc.). In notebooks or scripts without an `lllm.toml`, import them manually:

```python
from lllm.proxies import load_builtin_proxies

loaded, errors = load_builtin_proxies()
print(f"Loaded: {loaded}")
print(f"Failed (missing deps): {errors}")
```

This imports each module in `BUILTIN_PROXY_MODULES`, triggering their `@ProxyRegistrator` decorators. Modules with missing optional dependencies (API keys, extra packages) fail silently — `errors` tells you which ones.

For selective loading:

```python
load_builtin_proxies(["lllm.proxies.builtin.wa_proxy", "lllm.proxies.builtin.fmp_proxy"])
```


## ProxyManager Runtime

The `ProxyManager` runtime class composes multiple `BaseProxy` subclasses into a single callable dispatcher:

```python
from lllm.proxies import ProxyManager

proxy_manager = ProxyManager(activate_proxies=["finance/fmp", "wa"], cutoff_date="2024-01-01")
result = proxy_manager("finance/fmp/search/search-symbol", {"query": "AAPL"})
result = proxy_manager("wa/Query/llm-api", {"input": "10 densest metals"})
```

### How Activation Matching Works

`ProxyManager(activate_proxies=[...])` iterates all resources with `resource_type == "proxy"` in the runtime and matches each against the activation list. A proxy matches if **any** of these equals an entry in `activate_proxies`:

- The qualified key (`"my_system.proxies:finance/fmp"`)
- The bare key (`"finance/fmp"`)
- The `_proxy_path` attribute set by `@ProxyRegistrator` (`"finance/fmp"`)

This means you can always use the short path regardless of how the proxy was registered.

When `activate_proxies` is empty (default), **all** registered proxies are loaded.

### Dispatch

`proxy_manager(endpoint, params)` resolves the endpoint string:

- `"finance/fmp/search/search-symbol"` → proxy `"finance/fmp"`, method `"search_symbol"`
- `"finance/fmp.search_symbol"` → same, using dot notation

### Features

- **Selective activation** — `activate_proxies` filters which proxies load; missing ones are silently skipped.
- **Cutoff dates** — `cutoff_date` enforces data availability constraints per proxy.
- **Deploy mode** — `deploy_mode=True` disables cutoffs for production.
- **Documentation** — `proxy.retrieve_api_docs()` returns human-readable endpoint docs that can be inserted into prompts.
- **Inventory** — `proxy.available()` returns sorted list of loaded proxy keys.

```python
proxy_manager = ProxyManager()
print(proxy_manager.available())           # what's loaded
print(proxy_manager.retrieve_api_docs())   # docs for prompt insertion
print(proxy_manager.api_catalog())         # structured directory
```

### Dynamic Registration

Add proxies to a running `ProxyManager` instance:

```python
proxy_manager.register("custom/my_api", MyAPIProxy)
```


## Writing a Proxy

A complete example (Wolfram Alpha, simplified):

```python
import os
from lllm.proxies import BaseProxy, ProxyRegistrator

@ProxyRegistrator(
    path="wa",
    name="Wolfram Alpha API",
    description="Query Wolfram Alpha for computations and factual answers.",
)
class WAProxy(BaseProxy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = os.getenv("WA_API_DEV")
        self.base_url = "https://www.wolframalpha.com/api/v1"

    @BaseProxy.endpoint(
        category="Query",
        endpoint="llm-api",
        name="Wolfram Alpha LLM API",
        description="Natural language query to Wolfram Alpha.",
        params={
            "input*": (str, "10 densest elemental metals"),
            "assumption": (str, None),
        },
        response={"response": "Input interpretation: ..."},
    )
    def query(self, params: dict) -> dict:
        return params   # BaseProxy handles the actual HTTP call
```

Key points:
- `__init__` receives `cutoff_date`, `activate_proxies`, `deploy_mode` via `**kwargs` from `BaseProxy.__init__`
- `@BaseProxy.endpoint` is metadata — it describes the endpoint for docs and auto-testing
- The `path` in `@ProxyRegistrator` is what users pass to `activate_proxies` and dispatch
- Additional docs (like Wolfram Alpha's assumptions guide) can be stored as package assets and loaded via the custom section system


## Proxy in Agent Systems

In a tactic, proxies are typically activated in the config and wired via the system code:

```yaml
# config.yaml
proxy_activation:
  - wa
  - finance/fmp
deploy_mode: false
cutoff_date: "2024-01-01"
```

```python
class ResearchSystem(Tactic):
    name = "research"
    agent_group = ["researcher"]

    def __init__(self, config, ckpt_dir, stream=None, runtime=None):
        super().__init__(config, ckpt_dir, stream, runtime)
        self.proxy_manager = ProxyManager(
            activate_proxies=config.get("proxy_activation", []),
            cutoff_date=config.get("cutoff_date"),
            deploy_mode=config.get("deploy_mode", False),
            runtime=self._runtime,
        )

    def call(self, task, **kwargs):
        # proxy.retrieve_api_docs() → insert into prompt for tool selection
        # proxy("wa/Query/llm-api", {"input": query}) → execute tool call
        ...
```

## Prompting


A prompt to use the API library can be provided to the agent's system prompt.

```markdown
## API Library Usage

You have access to an API library within your `<python_cell>` blocks. The system will execute these for you:

 **`CALL_API(api_path: str, api_params: dict)`**: Use this to call an API endpoint.
    * Example: `response = CALL_API("fmp/crypto/end-of-day/historical-price-eod/full", {{"symbol": "BTCUSD", "from": "2023-01-01"}}) `

A directory of available APIs is provided below.
1.  **Consult Documentation First**: ALWAYS make sure you have retrieved and read the documents of the API endpoints you 
are going to use *before* you write a Python cell that uses `CALL_API` function, unless you have retrieved that specific
documentation earlier in this session. This prevents incorrect API usage. 
2.  **Use `CALL_API`**: ALWAYS use the `CALL_API` function to interact with APIs. API keys are managed by the backend. 

## API Directory

---
```
{api_directory}
```
---

Additional Notes:
* Do not repeatedly request the same API documentation if you've already retrieved it.
* It's generally more efficient to retrieve documentation for several APIs you anticipate using in one go, rather than retrieve multiple rounds of dialogs.
```

The api_directory can be retrieved using the `proxy_manager.api_directory()` method. This can also done automatically through LLLM when using the sandbox or the proxy tool calling function (WIP).
