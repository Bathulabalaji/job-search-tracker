"""What every provider adapter must offer, and the plain data that flows across that line."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from app.llm.catalog import ModelSpec

# What `bind_tools` accepts: LangChain tools, Pydantic models, or raw JSON-schema dicts.
ToolLike = BaseTool | type[BaseModel] | dict[str, object]
EmbedKind = Literal["document", "query"]


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    estimated: bool = False  # True when the provider reported nothing and we guessed

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ChatReply:
    """One provider answer. Exactly one of `message` (complete) or `chunks` (streaming) is set.

    `headers` are the HTTP response headers when the SDK exposes them (Groq does), used by the
    ledger for live budget figures. `parsed` is the validated object for structured output.
    """

    message: AIMessage | None = None
    chunks: Iterator[AIMessageChunk] | None = None
    usage: Usage | None = None
    headers: dict[str, str] = field(default_factory=dict)
    parsed: BaseModel | None = None


class ChatProvider(Protocol):
    name: str

    def chat(
        self,
        spec: ModelSpec,
        messages: Sequence[BaseMessage],
        *,
        tools: Sequence[ToolLike] | None,
        schema: type[BaseModel] | None,
        stream: bool,
        timeout: float,
        max_tokens: int,
        temperature: float,
    ) -> ChatReply:
        """Raise only `app.llm.errors.LLMError` subclasses."""
        ...

    def embed(
        self,
        spec: ModelSpec,
        texts: Sequence[str],
        *,
        kind: EmbedKind,
        dims: int,
        timeout: float,
    ) -> list[list[float]]:
        """Raise only `app.llm.errors.LLMError` subclasses."""
        ...


def usage_from_message(message: AIMessage | AIMessageChunk) -> Usage | None:
    metadata = message.usage_metadata
    if not metadata:
        return None
    return Usage(
        prompt_tokens=int(metadata.get("input_tokens", 0)),
        completion_tokens=int(metadata.get("output_tokens", 0)),
    )


def message_content_text(message: BaseMessage) -> str:
    """The visible text of a message (not its tool calls)."""
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and part.get("type", "text") == "text":
            parts.append(str(part.get("text", "")))
    return "".join(parts)


def as_chunk(message: AIMessage) -> AIMessageChunk:
    """Streams typed as `Iterator[AIMessage]` yield chunks in practice; make that explicit."""
    if isinstance(message, AIMessageChunk):
        return message
    return AIMessageChunk(
        content=message.content,
        tool_calls=message.tool_calls,
        usage_metadata=message.usage_metadata,
        response_metadata=message.response_metadata,
        id=message.id,
    )
