"""Token estimates without a tokenizer.

Providers report exact usage after every call; these estimates only decide which model can take
a prompt and how much budget to reserve beforehand. They lean high (3.6 characters per token)
so a Groq model is never handed a prompt that its per-minute token budget cannot fit.
"""

import json
from collections.abc import Iterable
from math import ceil

from langchain_core.messages import BaseMessage

CHARS_PER_TOKEN = 3.6
MESSAGE_OVERHEAD_TOKENS = 4


def estimate_tokens(text: str, chars_per_token: float = CHARS_PER_TOKEN) -> int:
    if not text:
        return 0
    return max(1, ceil(len(text) / chars_per_token))


def message_text(message: BaseMessage) -> str:
    """The text a message contributes to a prompt, including serialized tool calls."""
    parts: list[str] = []
    content = message.content
    if isinstance(content, str):
        parts.append(content)
    else:
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                parts.append(str(text) if text else json.dumps(part, default=str))
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        parts.append(json.dumps(tool_calls, default=str))
    return "\n".join(parts)


def estimate_messages(
    messages: Iterable[BaseMessage], chars_per_token: float = CHARS_PER_TOKEN
) -> int:
    return sum(
        estimate_tokens(message_text(m), chars_per_token) + MESSAGE_OVERHEAD_TOKENS
        for m in messages
    )


def estimate_json(value: object, chars_per_token: float = CHARS_PER_TOKEN) -> int:
    """For tool schemas and structured-output schemas, which also count as prompt tokens."""
    return estimate_tokens(json.dumps(value, default=str), chars_per_token)
