"""Level-2 prompt from chain_b."""
from lllm.core.prompt import Prompt

level2 = Prompt(
    path="level2",
    prompt="I am level-2 from chain_b, built on chain_c and chain_d.",
)
