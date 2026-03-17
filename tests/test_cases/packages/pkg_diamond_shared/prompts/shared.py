"""Shared prompt — should only be registered once even if two packages depend on it."""
from lllm.core.prompt import Prompt

shared_base = Prompt(
    path="shared_base",
    prompt="I am the shared base prompt, loaded exactly once.",
)
