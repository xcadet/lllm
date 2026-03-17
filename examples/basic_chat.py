"""
Basic chat example — no configuration required.

Prerequisites:
    pip install lllm-core
    export OPENAI_API_KEY=sk-...   # or ANTHROPIC_API_KEY, etc.
"""
from lllm import Tactic

agent = Tactic.quick("You are a helpful assistant.", model="gpt-4o")
agent.open("chat")
agent.receive("What is the capital of France?")
print(agent.respond().content)
