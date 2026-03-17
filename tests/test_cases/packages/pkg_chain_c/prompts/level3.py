"""Level-3 prompt from chain_c."""
from lllm.core.prompt import Prompt

level3 = Prompt(
    path="level3",
    prompt="I am level-3 from chain_c, built on chain_d.",
)
