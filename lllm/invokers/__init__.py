from __future__ import annotations

from typing import Callable, Dict

from lllm.invokers.base import BaseInvoker
from lllm.invokers.openai import OpenAIInvoker

InvokerBuilder = Callable[[Dict], BaseInvoker]

_PROVIDER_BUILDERS: Dict[str, InvokerBuilder] = {
    "openai": lambda cfg: OpenAIInvoker(cfg),
}


def register_invoker(name: str, builder: InvokerBuilder, *, overwrite: bool = False) -> None:
    name = name.lower()
    if name in _PROVIDER_BUILDERS and not overwrite:
        raise ValueError(f"Invoker '{name}' already registered")
    _PROVIDER_BUILDERS[name] = builder


def build_invoker(config: Dict) -> BaseInvoker:
    invoker_name = config.get("invoker", "openai").lower()
    try:
        builder = _PROVIDER_BUILDERS[invoker_name]
    except KeyError as exc:
        raise KeyError(
            f"Invoker '{invoker_name}' not registered. Available: {sorted(_PROVIDER_BUILDERS)}"
        ) from exc
    invoker_config = config.get("invoker_config", config)
    return builder(invoker_config)


__all__ = ["register_invoker", "build_invoker", "InvokerBuilder"]
