"""Root prompt that sits atop the diamond dependency."""
from lllm.core.prompt import Prompt

root_prompt = Prompt(
    path="root_prompt",
    prompt="I am the root, depending on left and right (which both share the shared package).",
)
