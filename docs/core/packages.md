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

### Format

An lllm.toml have five official sections: [package], [prompts], [proxies], [configs], [tactics], and [dependencies]. And you can have your own custom sections like [my_custom_section], [assets], etc.

- [package]: the name of the "package", version, description, etc. Note that this is not the name of the project, but the name of the "package" that you are encapsulating. All the prompts, proxies, configs, and tactics you put in this toml file will be encapsulated under this package, even if they are in another package, and they will work under the namespace (prefix) of this package.
- [prompts]: the folders of the prompts, if not specified, the LLLM will look for the prompts/ in the same folder as the lllm.toml.
- [proxies]: the folders of the proxies, if not specified, the LLLM will look for the proxies/ in the same folder as the lllm.toml.
- [configs]: the folders of the configs, if not specified, the LLLM will look for the configs/ in the same folder as the lllm.toml.
- [tactics]: the folders of the tactics, if not specified, the LLLM will look for the tactics/ in the same folder as the lllm.toml.
- [dependencies]: the dependencies of the package, which are name or path of other packages, which will indexed by their names. If not specified, the LLLM will not load any dependencies.

For example, your file structure is as follows:
```
project_name/
├── lllm.toml         
├── lllm_packages/    
  ├── my_package1/ 
        ├── lllm.toml       
  ├── my_package2/       
├── ... (other files and folders like your application code, data, etc.)

shared_lllm_packages/
  ├── shared_package1/ 
        ├── lllm.toml       
```

Say your lllm.toml (project_name/lllm.toml) is like this:

```
[package]
name = "my_system"
version = "0.0.1"
description = "A system for building agentic systems"

[dependencies]
packages = ["./lllm_packages/my_package1", "./lllm_packages/my_package2", "../shared_lllm_packages/shared_package1"]
```

and the lllm.toml of my_package1, my_package2, and shared_package1 are like this (the package name is the name of the folder):
```
# my_package1/lllm.toml
[package]
name = "my_package1"
version = "0.0.1"
description = "A package for building agentic systems"

# my_package2/lllm.toml
[package]
name = "my_package2"

# shared_package1/lllm.toml
[package]
name = "shared_package1"
```

Then you will have four packages loaded into the runtime: my_system, my_package1, my_package2, and shared_package1. And you can access the resources by like `load_tactic("my_package1:my_tactic1")`, `load_prompt("my_package2:folder1/my_prompt1")`, `load_proxy("shared_package1:my_proxy1")`, `load_config("my_package1:folder3/my_config1")`. Or like `load(my_package1.tactics:my_tactic1)`, `load(my_package2.prompts:my_prompt1)`, `load(shared_package1.proxies:my_proxy1)`, `load(my_package1.configs:my_config1)`. Whichever way you prefer, just remember to use the `:` to separate the package name and the resource name, and the `.` to index inside the package (for example, you may use it to access an asset in a package such as an image like `load(my_package1.assets:image.png)`), and the `/` to index inside the resource. Note that since you are purely loading by dependency, so there will be no resources under the my_system package.

However, if you load in this way:

```
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

Then the resources from my_package1, my_package2, and shared_package1 will all be loaded into my_system's namespace besides their own namespaces (i.e., my_package1, my_package2, and shared_package1, as they are set in the dependencies), and you can access them by like `load_tactic("my_tactic1")`, `load_prompt("my_prompt1")`, `load_proxy("my_proxy1")`, `load_config("my_config1")`, or `load_tactic("my_package1:my_tactic1")`, `load_prompt("my_package2:my_prompt1")`, `load_proxy("shared_package1:my_proxy1")`, `load_config("my_package1:my_config1")`, or `load_tactic("my_system:my_package1:my_tactic1")`, `load_prompt("my_system:my_package2:my_prompt1")`, `load_proxy("my_system:shared_package1:my_proxy1")`, `load_config("my_system:my_package1:my_config1")`.

However, there will be the risk of name collision, thus, you can name an alias in the toml file, using the `as` keyword for packages/dependencies and `under` keyword for resources like this:
```
[package]
name = "my_system"
version = "0.0.1"
description = "A system for building agentic systems"
default_namespace = "my_system"

[tactics]
paths = ["./lllm_packages/my_package1/tactics under custom_pkg1", "./lllm_packages/my_package2/tactics under custom_pkg2", "../shared_lllm_packages/shared_package1/tactics"]

[prompts]
paths = ["./lllm_packages/my_package1/prompts", "./lllm_packages/my_package2/prompts under custom_pkg1", "../shared_lllm_packages/shared_package1/prompts under custom_pkg2"]

[dependencies]
packages = ["./lllm_packages/my_package1 as pkg1", "./lllm_packages/my_package2 as pkg2", "../shared_lllm_packages/shared_package1 as pkg3"]
```

Then you will have six namespaces: my_system, tactics_pkg1, tactics_pkg2, pkg1, pkg2, pkg3 (there might be redundant resources as in this example). And the default namespace is my_system, but it can also be modified to other namespaces, e.g., `default_namespace = "tactics_pkg1"`, which will be used to interpret any prefix-free paths. 
