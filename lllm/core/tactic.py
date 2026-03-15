from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
import inspect
import datetime as dt
from enum import Enum
import logging
logging.basicConfig(level=logging.INFO)

from lllm.core.agent import Agent
from lllm.core.runtime import Runtime, get_default_runtime
from lllm.core.config import auto_discover_if_enabled
from lllm.invokers import build_invoker
import lllm.utils as U
from lllm.core.const import APITypes
from lllm.core.log import build_log_base



# ---------------------------------------------------------------------------
# Agent registration and building
# ---------------------------------------------------------------------------



def _normalize_tactic_type(tactic_type):
    if isinstance(tactic_type, Enum) or (isinstance(tactic_type, type) and issubclass(tactic_type, Enum)):
        return tactic_type.value
    elif isinstance(tactic_type, str):
        return tactic_type
    else:
        raise ValueError(f"Invalid tactic type: {tactic_type}")

def register_tactic_class(tactic_cls: Type['Tactic'], runtime: Runtime = None) -> Type['Tactic']:
    runtime = runtime or get_default_runtime()
    tactic_type = _normalize_tactic_type(getattr(tactic_cls, 'tactic_type', None))
    assert tactic_type not in (None, ''), f"Tactic class {tactic_cls.__name__} must define `tactic_type`"
    if tactic_type in runtime.tactics and runtime.tactics[tactic_type] is not tactic_cls:
        raise ValueError(f"Tactic type '{tactic_type}' already registered with {runtime.tactics[tactic_type].__name__}")
    runtime.register_tactic(tactic_type, tactic_cls)
    return tactic_cls

def get_tactic_class(tactic_type: str, runtime: Runtime = None) -> Type['Tactic']:
    runtime = runtime or get_default_runtime()
    if tactic_type not in runtime.tactics:
        raise KeyError(f"Tactic type '{tactic_type}' not found. Registered: {list(runtime.tactics.keys())}")
    return runtime.tactics[tactic_type]

def build_tactic(config: Dict[str, Any], ckpt_dir: str, stream, tactic_type: str = None, runtime: Runtime = None, **kwargs) -> 'Tactic':
    if tactic_type is None:
        tactic_type = config.get('tactic_type')
    tactic_type = _normalize_tactic_type(tactic_type)
    tactic_cls = get_tactic_class(tactic_type, runtime)
    return tactic_cls(config, ckpt_dir, stream, **kwargs)


class Tactic:
    """
    Tactic is the **top-level** abstraction from LLLM, and the uppermost interface to build an agentic system.
    An agentic system is defined by a group of agents (≈ system prompt + base model, the “callers”), 
    a set of prompts (the "functions" or "calls"), and the tactic (the "program" that wire the callers and functions). 

    Tactic defines the "program" that defines how the "agents" handle a task, i.e. how the callers (agents) and functions (prompts) are worked together.
    Tactic is "local" and "functional" in the sense that it should carry a specific task, and serve as a building block for the agentic system.
    Given tactics, the upper agentic system is more about a glue code to connect to your own workflow, or like for hosting as a service.
    """
    name: str # a name for this tactic, like "research", "planning", "execution", etc.
    agent_group: List[str] = None # the keys to find the agent configs from the registry
    is_async: bool = False

    def __init_subclass__(cls, register: bool = True, runtime: Optional[Runtime] = None, **kwargs):
        runtime = runtime or get_default_runtime()
        super().__init_subclass__(**kwargs)
        if register:
            register_tactic_class(cls, runtime=runtime)

    def __init__(self, config: Dict[str, Any], ckpt_dir: str, stream = None, runtime: Optional[Runtime] = None):
        self._runtime = runtime or get_default_runtime()
        auto_discover_if_enabled(config.get("auto_discover"), runtime=self._runtime)
        if stream is None:
            stream = U.PrintSystem()
        self.config = config
        assert self.agent_group is not None, f"Agent group is not set for {self.tactic_type}"
        _agent_group_configs = config['agent_group_configs']
        self.agent_group_configs = {}
        for agent_type in self.agent_group:
            assert agent_type in _agent_group_configs, f"Agent type {agent_type} not found in agent group configs"
            self.agent_group_configs[agent_type] = _agent_group_configs[agent_type]
        self._stream = stream
        self._stream_backup = stream
        self.st = None
        self.ckpt_dir = ckpt_dir
        self._log_base = build_log_base(config)
        self.agents = {}

        # Initialize Invoker via runtime
        self.llm_invoker = build_invoker(config)

        for agent_name, model_config in self.agent_group_configs.items():
            model_config = model_config.copy()
            self.model = model_config.pop('model_name')
            system_prompt_path = model_config.pop('system_prompt_path')
            api_type_value = model_config.pop('api_type', APITypes.COMPLETION.value)
            if isinstance(api_type_value, APITypes):
                api_type = api_type_value
            else:
                api_type = APITypes(api_type_value)
            
            self.agents[agent_name] = Agent(
                name=agent_name,
                system_prompt=self._runtime.get_prompt(system_prompt_path),
                model=self.model,
                llm_invoker=self.llm_invoker,
                api_type=api_type,
                model_args=model_config,
                log_base=self._log_base,
                max_exception_retry=self.config.get('max_exception_retry', 3),
                max_interrupt_steps=self.config.get('max_interrupt_steps', 5),
                max_llm_recall=self.config.get('max_llm_recall', 0),
            )

        self.__additional_args = {}
        sig = inspect.signature(self.call)
        for arg in sig.parameters:
            if arg not in {'task', '**kwargs'}:
                self.__additional_args[arg] = sig.parameters[arg].default

    def set_st(self, session_name: str):
        self.st = U.StreamWrapper(self._stream, self._log_base, session_name)

    def restore_st(self):
        pass

    def silent(self):
        self._stream = U.PrintSystem(silent=True)

    def restore(self):
        self._stream = self._stream_backup

    def call(self, task: str, **kwargs):
        raise NotImplementedError

    def __call__(self, task: str, session_name: str = None, **kwargs) -> str:
        if session_name is None:
            session_name = task.replace(' ', '+')+'_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.set_st(session_name)
        report = self.call(task, **kwargs)
        with self.st.expander('Prediction Overview', expanded=True):
            self.st.code(f'{report}')
        self.restore_st()
        return report
