"""A scripted provider for tests and local development without API keys.

Each `chat` call consumes the next step: an `AIMessage` to return, an exception to raise, or a
callable given the recorded call. With no steps left it echoes a short reply. Embeddings are
deterministic (hash-based) so similarity tests are repeatable.
"""

import hashlib
import math
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from pydantic import BaseModel

from app.llm.catalog import ModelSpec
from app.llm.providers.base import ChatReply, EmbedKind, ToolLike, Usage, usage_from_message
from app.llm.tokens import estimate_messages, estimate_tokens


@dataclass
class FakeCall:
    model: str
    messages: list[BaseMessage]
    tools: list[ToolLike]
    schema: type[BaseModel] | None
    stream: bool
    max_tokens: int


@dataclass
class FakeStep:
    """A scripted reply with optional headers, or an exception to raise instead."""

    message: AIMessage | None = None
    error: Exception | None = None
    headers: dict[str, str] = field(default_factory=dict)
    parsed: BaseModel | None = None


Step = AIMessage | Exception | FakeStep | Callable[[FakeCall], AIMessage]


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        name: str = "fake",
        steps: Iterable[Step] = (),
        *,
        embed_error: Exception | None = None,
        default_reply: str = "ok",
    ) -> None:
        self.name = name
        self.steps: deque[Step] = deque(steps)
        self.calls: list[FakeCall] = []
        self.embed_calls: list[list[str]] = []
        self.embed_error = embed_error
        self.default_reply = default_reply

    def script(self, *steps: Step) -> None:
        self.steps.extend(steps)

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
        call = FakeCall(
            model=spec.name,
            messages=list(messages),
            tools=list(tools or ()),
            schema=schema,
            stream=stream,
            max_tokens=max_tokens,
        )
        self.calls.append(call)
        step: Step = self.steps.popleft() if self.steps else AIMessage(content=self.default_reply)
        if isinstance(step, Exception):
            raise step
        if callable(step) and not isinstance(step, AIMessage | FakeStep):
            step = step(call)
        fake = step if isinstance(step, FakeStep) else FakeStep(message=step)
        if fake.error is not None:
            raise fake.error
        message = fake.message or AIMessage(content=self.default_reply)
        usage = usage_from_message(message) or Usage(
            prompt_tokens=estimate_messages(messages),
            completion_tokens=estimate_tokens(str(message.content)),
            estimated=True,
        )
        if stream:
            return ChatReply(chunks=self._chunks(message, usage), headers=dict(fake.headers))
        return ChatReply(
            message=message, usage=usage, headers=dict(fake.headers), parsed=fake.parsed
        )

    @staticmethod
    def _chunks(message: AIMessage, usage: Usage) -> Iterator[AIMessageChunk]:
        text = str(message.content)
        words = text.split(" ")
        for index, word in enumerate(words):
            piece = word if index == len(words) - 1 else word + " "
            yield AIMessageChunk(content=piece)
        yield AIMessageChunk(
            content="",
            tool_calls=message.tool_calls,
            usage_metadata={
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            },
        )

    def embed(
        self,
        spec: ModelSpec,
        texts: Sequence[str],
        *,
        kind: EmbedKind,
        dims: int,
        timeout: float,
    ) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        if self.embed_error is not None:
            raise self.embed_error
        return [fake_embedding(text, dims) for text in texts]


def fake_embedding(text: str, dims: int) -> list[float]:
    """A unit vector derived from the text's words, so similar texts land close together."""
    vector = [0.0] * dims
    for word in text.lower().split():
        digest = hashlib.sha256(word.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        vector[index] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]
