"""Base prompt from chain_d (bottom of dependency chain)."""
from lllm.core.prompt import Prompt

foundation = Prompt(
    path="foundation",
    prompt="I am the foundation prompt from chain_d.",
)
