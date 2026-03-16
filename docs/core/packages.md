# Packages

LLLM is Pythonic, while LLLM itself is self-contained, and you can just use it as a library and organize your own code as you want. However, it is recommended to separate the LLLM resources (prompts, proxies, configs, and tactics) from the upper-level system by encapsulating them into a package for better organization and reusability.

An LLLM package is structured as follows:

```
package_name/
  ├── prompts/        # the prompts, for the agents to call, i.e., the functions or "calls"
  ├── proxies/        # the proxies, for proxy-based tool-calling, mini in-dialog interpreter
  ├── configs/        # the configs for the agents, i.e., the base models, system prompts, etc.
  ├── tactics/        # the tactics, which are the programs that wire the agents and prompts together
  ├── lllm.toml       # the metadata for the encapsulation, also for solving the dependency issues, etc.
```

An example structure of an LLLM agentic system is as follows:

```
project_name/
├── lllm.toml         # to help LLLM find the prompts, proxies, configs, and tactics, etc.
├── lllm_packages/    # a folder that contains the LLLM packages, you can put it anywhere as long as lllm.toml can find it.
  ├── my_package1/      
  ├── my_package2/       
├── ... (other files and folders like your application code, data, etc.)
```

Conceptually, LLLM maintains a huge registry of prompts, proxies, configs, and tactics, either local or shared, which are loaded on demand through the lllm.toml file. All the resources (prompts, proxies, agents, and tactics) are indexed by "URLs". When you are building an agentic system, you usually use tactics as the building blocks or modules, and use them to compose your own agentic system. It works in this way, the tactic find agent configs by keys, and finds prompts including system prompts from prompt registry. Then the proxy-based tool-calling is through the proxy registry. 


## lllm.toml

lllm.toml defines a "node" of a dependency tree of lllm packages. Theoretically, you just need to put a single lllm.toml in your project root to load/link to the lllm packages, then you should be able to access all the resources in the project that you designated with no actual LLLM code in your project (as they can be in other places).

The purpose of an lllm.toml is to help LLLM load the resources (prompts, proxies, configs, and tactics) to the runtime of the project. By default, the LLLM will look for the lllm.toml in the project root to build the default runtime. You can manually specify other {yourname}.toml to build the runtime for your own project. Or building multiple runtimes for different purposes.

### Runtime Initialization

By default, when LLLM is imported, it looks for `lllm.toml` starting from the current working directory and searching upward. If found, it loads the package tree into the default runtime. If no `lllm.toml` is found, the default runtime is initialized empty (useful for fast mode and testing), and a log-level info message is emitted.

Users can also create named runtimes from specific toml files:

```python
from lllm import load_runtime, get_runtime

# Auto-load from project root into default runtime (happens on import)
from lllm import load_prompt  # default runtime already populated

# Explicit load / replace default runtime
load_runtime("path/to/custom.toml")

# Named runtimes for parallel experiments
load_runtime("experiment_a/lllm.toml", name="exp_a")
load_runtime("experiment_b/lllm.toml", name="exp_b")
rt_a = get_runtime("exp_a")
rt_b = get_runtime("exp_b")
```


### Resources

In an LLLM package, you have four types of major resources: prompts, proxies, configs, and tactics, and optionally, you can pack your own custom resources into a package as a custom section. Every resource is internally attached to a `ResourceNode` object, which is automatically created once a Prompt, Proxy, Config, or Tactic is loaded into the runtime which manages a URL-based index of the resource tree. 

`ResourceNode` is a wrapper, not a base class — it wraps the actual resource object (Prompt, Tactic class, config dict, etc.) and holds registry metadata (qualified key, namespace, resource type, lazy loader). The existing classes (Prompt, Tactic, BaseProxy) do not need to inherit from it.

For eager resources (prompts, tactics discovered at import time), the value is set immediately. For lazy resources (configs, custom assets), the `ResourceNode` holds a loader callable and the actual value is only read on first access, then cached.

To make a general resource recognizable, you can use the `resource` decorator to decorate your custom resource class, with the loading happening in the `__init__` method, and LLLM will automatically recognize it as a resource. 

Then you can load it by `load_resource("my_package1.my_custom_section:my_custom_resource")`. See the Format section below for more details.


### Format

An lllm.toml has six official sections: [package], [prompts], [proxies], [configs], [tactics], and [dependencies]. You can also define custom sections like [my_custom_section], [assets], etc.

- [package]: the name of the "package", version, description, etc. Note that this is not the name of the project, but the name of the "package" that you are encapsulating. All the prompts, proxies, configs, and tactics you put in this toml file will be encapsulated under this package, even if they are in another package, and they will work under the namespace (prefix) of this package.
- [prompts]: the folders of the prompts, if not specified, LLLM will look for `prompts/` in the same folder as the lllm.toml. If no `[prompts]` section is present and no `prompts/` subfolder exists, this section is simply empty.
- [proxies]: the folders of the proxies, if not specified, LLLM will look for `proxies/` in the same folder as the lllm.toml. If no `[proxies]` section is present and no `proxies/` subfolder exists, this section is simply empty.
- [configs]: the folders of the configs, if not specified, LLLM will look for `configs/` in the same folder as the lllm.toml. Configs are YAML files loaded lazily — the file is only read on first access. If no `[configs]` section is present and no `configs/` subfolder exists, this section is simply empty.
- [tactics]: the folders of the tactics, if not specified, LLLM will look for `tactics/` in the same folder as the lllm.toml. If no `[tactics]` section is present and no `tactics/` subfolder exists, this section is simply empty.
- [dependencies]: the dependencies of the package, which are name or path of other packages, which will be indexed by their names. If not specified, LLLM will not load any dependencies. Dependencies are loaded into their own namespace only. To re-export a dependency's resources into the current package namespace, list their paths explicitly in the relevant resource section.


### Resource Indexing

The resources (prompts, proxies, configs, tactics, and other custom sections besides [package], [dependencies]) are indexed by a URL with the format `<package_path>:<resource_path>`. There is always exactly one `:` separator in the URL.

The `package_path` has the format `<package_name>.<section_name>`, and the `resource_path` has the format `<folder_name>/<sub_folder_name>/.../<file_name>/<resource_name>`.

When a key collision occurs during discovery (two paths producing the same resource key), LLLM logs a warning identifying both sources. The later registration overwrites the earlier one. Use the `under` keyword (see Alias Loading) to disambiguate.


#### Example: Prompt Indexing

You have two prompts folders loaded into the `prompts` section of package `my_package1` like `[prompts] paths = [".../<path_to_prompts_1>/prompts_1", ".../<path_to_prompts_2>/prompts_2"]`, and they have the following structure:
```
prompts_1/
├── my_prompts1.py
├── sub_folder1/
    ├── sub_folder2/
        ├── my_prompts2.py

# in some other place
prompts_2/
├── sub_folder3/
    ├── my_prompts3.py
```
And say each of the prompts files (my_prompts1.py to my_prompts3.py) have two prompts, all named as `my_prompt1`, `my_prompt2`. Then the full URLs of the resources are:
- `my_package1.prompts:my_prompts1/my_prompt1`
- `my_package1.prompts:my_prompts1/my_prompt2`
- `my_package1.prompts:sub_folder1/sub_folder2/my_prompts2/my_prompt1`
- `my_package1.prompts:sub_folder1/sub_folder2/my_prompts2/my_prompt2`
- `my_package1.prompts:sub_folder3/my_prompts3/my_prompt1`
- `my_package1.prompts:sub_folder3/my_prompts3/my_prompt2`

Note that their root folders (`prompts_1`, `prompts_2`) are omitted in the URLs. After loading, they are all indexed in a flat structure, which was done through recursively traversing each provided path, just like putting all the files in a single `prompts` folder.


#### Convenience Access Functions

You can access resources by a full URL using the `load_resource` function. `load_resource` **always** requires the section name in the package path:

```python
# Full URL — always works
load_resource("my_package1.prompts:my_prompts1/my_prompt1")

# Section-only (no dot) — interpreted as section of the default package
load_resource("prompts:my_prompts1/my_prompt1")
# equivalent to: load_resource("my_system.prompts:my_prompts1/my_prompt1")
# when my_system is the default package
```

For the four built-in resource types, typed convenience functions allow omitting the section name:

```python
# With package name — section inferred from function
load_prompt("my_package1:my_prompts1/my_prompt1")

# Without package name — uses default package
load_prompt("my_prompts1/my_prompt1")
```

You can implement your own convenience functions to load resources from custom sections.


### Resource Loading

#### Example: Dependency-Only Loading

```
project_name/
├── lllm.toml         
├── lllm_packages/    
  ├── my_package1/ 
        ├── lllm.toml       
  ├── my_package2/       
├── ...

shared_lllm_packages/
  ├── shared_package1/ 
        ├── lllm.toml       
```

Say your lllm.toml (project_name/lllm.toml) is:

```toml
[package]
name = "my_system"
version = "0.0.1"
description = "A system for building agentic systems"

[dependencies]
packages = ["./lllm_packages/my_package1", "./lllm_packages/my_package2", "../shared_lllm_packages/shared_package1"]
```

and the dependency lllm.toml files are:
```toml
# my_package1/lllm.toml
[package]
name = "my_package1"
version = "0.0.1"

# my_package2/lllm.toml
[package]
name = "my_package2"

# shared_package1/lllm.toml
[package]
name = "shared_package1"
```

Then four packages are loaded into the runtime: my_system, my_package1, my_package2, and shared_package1. Since you are only loading by dependency, there are no resources under the my_system package — each dependency's resources live in their own namespace:

```python
load_tactic("my_package1:my_tactic1")
load_prompt("my_package2:folder1/my_prompt1")
load_proxy("shared_package1:my_proxy1")
load_config("my_package1:folder3/my_config1")
```


#### Example: Re-Exporting Into the Current Namespace

If you also list paths explicitly in the resource sections:

```toml
[package]
name = "my_system"
version = "0.0.1"
description = "A system for building agentic systems"

[prompts]
paths = ["./lllm_packages/my_package1/prompts", "./lllm_packages/my_package2/prompts", "../shared_lllm_packages/shared_package1/prompts"]

[proxies]
paths = ["./lllm_packages/my_package1/proxies", "./lllm_packages/my_package2/proxies", "../shared_lllm_packages/shared_package1/proxies"]

[configs]
paths = ["./lllm_packages/my_package1/configs", "./lllm_packages/my_package2/configs", "../shared_lllm_packages/shared_package1/configs"]

[tactics]
paths = ["./lllm_packages/my_package1/tactics", "./lllm_packages/my_package2/tactics", "../shared_lllm_packages/shared_package1/tactics"]

[dependencies]
packages = ["./lllm_packages/my_package1", "./lllm_packages/my_package2", "../shared_lllm_packages/shared_package1"]
```

Then the resources are loaded into **both** my_system's namespace (via the explicit paths) and each dependency's own namespace (via the dependency declarations). Since my_system is the default package, you can access resources with or without the package prefix:

```python
# Via default package namespace (my_system) — prefix omitted
load_tactic("my_tactic1")
load_prompt("my_prompt1")

# Via dependency namespace — always works
load_tactic("my_package1:my_tactic1")
load_prompt("my_package2:my_prompt1")

# Via full URL
load_resource("my_system.tactics:my_tactic1")
load_resource("my_package1.prompts:my_prompt1")
```


### Alias Loading

Name collisions can occur when multiple sources produce resources with the same key. Two aliasing mechanisms address this:

- `as` on dependencies — creates an **additional** alias for a package. The original package name still works.
- `under` on resource paths — adds a virtual root folder prefix to all resources from that path, within the *importing* package's namespace.

Both keywords can be specified either as inline strings (using the `as` / `under` keywords) or as standard TOML inline tables (using `alias` / `prefix` keys). The two forms are exactly equivalent — use whichever you prefer:

```toml
# String keyword form — convenient for simple cases
packages = ["./lllm_packages/my_package1 as pkg1"]
paths = ["./some/path under vfolder1"]

# TOML inline table form — standard TOML, works with any path
packages = [{path = "./lllm_packages/my_package1", alias = "pkg1"}]
paths = [{path = "./some/path", prefix = "vfolder1"}]
```

The table form also accepts the keyword names as keys (`as` and `under`) for consistency:

```toml
packages = [{path = "./lllm_packages/my_package1", as = "pkg1"}]    # same as alias = "pkg1"
paths = [{path = "./some/path", under = "vfolder1"}]                 # same as prefix = "vfolder1"
```


#### Alias Example

```toml
[package]
name = "my_system"
version = "0.0.1"
description = "A system for building agentic systems"

[tactics]
paths = ["./lllm_packages/my_package1/tactics under vfolder1", "./lllm_packages/my_package2/tactics under vfolder2", "../shared_lllm_packages/shared_package1/tactics"]

[prompts]
paths = ["./lllm_packages/my_package1/prompts", "./lllm_packages/my_package2/prompts under vfolder1", "../shared_lllm_packages/shared_package1/prompts under vfolder2"]

[dependencies]
packages = ["./lllm_packages/my_package1 as pkg1", "./lllm_packages/my_package2 as pkg2", "../shared_lllm_packages/shared_package1 as pkg3"]
```

This creates four package-level namespaces: my_system (default, omittable), pkg1, pkg2, pkg3. The `as` keyword creates an additional alias — the original names (my_package1, my_package2, shared_package1) still work.

The `under` keyword creates virtual root folders **within my_system's namespace**. It does not affect the dependency's own namespace:

```python
# Tactics from my_package1's folder, re-exported into my_system with vfolder1 prefix:
load_tactic("vfolder1/my_tactic1")                    # via my_system (default)
load_tactic("my_system:vfolder1/my_tactic1")           # explicit — same thing

# Same tactic via my_package1's own namespace (no vfolder prefix there):
load_tactic("my_package1:my_tactic1")                  # via original name
load_tactic("pkg1:my_tactic1")                         # via alias

# Tactics from shared_package1, re-exported into my_system without prefix:
load_tactic("shared_tactic1")                          # via my_system (default)
load_tactic("pkg3:shared_tactic1")                     # via alias

# Prompts from my_package2, re-exported with vfolder1 prefix:
load_prompt("vfolder1/my_prompt1")                     # via my_system (default)
load_prompt("my_package2:my_prompt1")                  # via own namespace (no prefix)
load_prompt("pkg2:my_prompt1")                         # via alias (no prefix)
```

Note: `under` modifies how resources appear in the **importing** package's namespace, not in the source package's own namespace.