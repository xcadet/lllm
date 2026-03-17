"""Left branch prompt."""
from lllm.core.prompt import Prompt

left_prompt = Prompt(
    path="left_prompt",
    prompt="I am the left branch, depending on shared.",
)
