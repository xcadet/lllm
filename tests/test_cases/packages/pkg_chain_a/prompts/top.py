"""Top-level prompt from chain_a."""
from lllm.core.prompt import Prompt

top = Prompt(
    path="top",
    prompt="I am the top-level prompt from chain_a.",
)
