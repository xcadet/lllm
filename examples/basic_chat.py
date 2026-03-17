"""
Basic chat example — no configuration required.

Prerequisites:
    export OPENAI_API_KEY=sk-...   # or ANTHROPIC_API_KEY, etc.
"""
from lllm import Tactic


# One-line chat
response = Tactic.quick("What is the capital of France?")
print(response.content)

# Get the agent and chat
response, agent = Tactic.quick("What is the capital of France?", return_agent=True)
print(response.content)
print(agent.name)

# Get the agent only
agent = Tactic.quick() # by default the system prompt is "You are a helpful assistant."
print(agent.name)

# Get the agent and chat with a custom system prompt
agent = Tactic.quick(system_prompt="You are a helpful assistant.", model="gpt-4o")
agent.open("chat")
agent.receive("What is the capital of France?")
print(agent.respond().content)

# Chat with a custom system prompt 
response = Tactic.quick("What is the capital of France?", system_prompt="You are a helpful assistant.")
print(response.content)

# Chat with a custom system prompt and get the agent
response, agent = Tactic.quick("What is the capital of France?", system_prompt="You are a helpful assistant.", return_agent=True)
print(response.content)
print(agent.name)