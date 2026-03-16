# Agent Configuration 

Agent config is the way to configure the base agent. It is written in yaml format, and can be inherited and extended in a recursive key-overriding manner through a special `base` key. The configs are stored in the `configs` section of the lllm.toml file. The filename is the name of the config, and the path is the path to the config file. You can set the base by its filename and path. 

The Tactic will use the agent configs to build the agent instance. Each agent config has a name, a model, a system prompt path, the api type, and a set of model arguments, as well as some extra settings. It has this structure, an optional base config and a global config, and the agent configs:
```yaml
base: ... # the optional base config to inherit from, see example below
global: # the default global settings for all the agents, optional, usually used to choose a default model and some model arguments.
   model_name: ... # the base model name to use, see invoker section for more details
   api_type: completion or response # the api type to use
   model_args:  # the model arguments
      temperature: ... # the temperature to use
      ... # other arguments, if not specified, will use the global config
   max_exception_retry: 3
   max_interrupt_steps: 5
   max_llm_recall: 3
   extra_settings: ... # the extra settings for the global config, reserved for advanced usage like context manager, etc.
agent_configs:
   - name: ... # the name of the agent config
     model_name: ... # the model to use
     system_prompt: ... # the system prompt to use, optional if system_prompt_path is provided
     system_prompt_path: ... # the path to the system prompt, optional if system_prompt is provided
     model_args:  # the model arguments
         ... # whatever argument you want to override the global config or add more arguments
     extra_settings: ... # the extra settings for the agent config, reserved for advanced usage like context manager, etc.
... # other possible keys, the user can choose to put whatever useful for their own usage.
```

## Inheritance

User can inherit the base config by using the `base` key. For example, if the configs folder has this structure:
```
configs/
  base.yaml
  agent_cfgs/
    agent1.yaml
    agent2.yaml
    sub_cfgs/
      sub1.yaml
      sub2.yaml
```
Then the agent1.yaml can inherit the base config by using the `base` key:

```yaml
# agent1.yaml
base: base # no need to use .yaml suffix
...
```
And the sub1.yaml can inherit the agent1 config (or whatever config you want to inherit from) by using the `base` key:

```yaml
# sub1.yaml
base: agent_cfgs/agent1
...
```

And if you wanna to further inherit the sub1 config, you can write as `agent_cfgs/sub_cfgs/sub1`. The inherence will recursively override the keys with precise matching until the very bottom level of the config. 