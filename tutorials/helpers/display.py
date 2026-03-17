"""
Pretty-print helpers for use inside tutorial notebooks.
"""

from __future__ import annotations
import textwrap


def print_section(title: str) -> None:
    bar = "=" * (len(title) + 4)
    print(f"\n{bar}")
    print(f"  {title}")
    print(f"{bar}\n")


def print_response(text: str, label: str = "Assistant") -> None:
    print(f"[{label}]")
    for line in textwrap.wrap(str(text), width=88):
        print(f"  {line}")
    print()


def print_dialog(dialog, max_messages: int = 20) -> None:
    """Render a lllm Dialog in a readable format."""
    messages = list(dialog)[:max_messages]
    for msg in messages:
        role = getattr(msg, "role", "?")
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        label = {"user": "User", "assistant": "Assistant", "system": "System"}.get(
            str(role), str(role)
        )
        prefix = ">>>" if label == "User" else "..."
        print(f"{prefix} [{label}] {str(content)[:200]}")
    if len(messages) < len(list(dialog)):
        print(f"    ... ({len(list(dialog)) - max_messages} more messages truncated)")
