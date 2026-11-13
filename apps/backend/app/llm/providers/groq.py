"""Groq through LangChain's `ChatGroq`.

Groq sends rate-limit headers on every response; LangChain does not surface them, so the
provider owns one `httpx.Client` with a response hook that records them per thread. The gateway
reads them from `ChatReply.headers` after each call and feeds the ledger.
"""

import threading
from collections.abc import Iterator, Sequence
from functools import lru_cache
from typing import Any

import httpx
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, SecretStr

from app.llm.catalog import ModelSpec
from app.llm.errors import LLMError, StructuredOutputInvalid
from app.llm.providers.base import ChatReply, EmbedKind, ToolLike, as_chunk, usage_from_message
from app.llm.providers.classify import classify_exception

_HEADER_PREFIXES = ("x-ratelimit", "retry-after")


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, *, http_client: httpx.Client | None = None) -> None:
        self._api_key = SecretStr(api_key)
        self._local = threading.local()
        self.http_client = http_client or httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0),
            event_hooks={"response": [self._capture_headers]},
        )

    # ---- ChatProvider ---------------------------------------------------------------------

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
        self._local.headers = {}
        model = self._model(spec, timeout=timeout, max_tokens=max_tokens, temperature=temperature)
        inputs = list(messages)
        try:
            if schema is not None:
                structured = model.with_structured_output(
                    schema, method="json_schema", include_raw=True
                )
                output = structured.invoke(inputs)
                return self._structured_reply(output)
            runnable = model.bind_tools(list(tools)) if tools else model
            if stream:
                reply = ChatReply(headers=self.last_headers())
                reply.chunks = self._wrap_stream(runnable.stream(inputs), reply, spec)
                return reply
            message = runnable.invoke(inputs)
            return ChatReply(
                message=message, usage=usage_from_message(message), headers=self.last_headers()
            )
        except LLMError:
            raise
        except Exception as exc:
            raise classify_exception(exc, provider=self.name, model=spec.name) from exc

    def embed(
        self,
        spec: ModelSpec,
        texts: Sequence[str],
        *,
        kind: EmbedKind,
        dims: int,
        timeout: float,
    ) -> list[list[float]]:
        raise classify_exception(
            NotImplementedError("Groq offers no embedding models"),
            provider=self.name,
            model=spec.name,
        )

    # ---- internals ------------------------------------------------------------------------

    def _model(
        self, spec: ModelSpec, *, timeout: float, max_tokens: int, temperature: float
    ) -> ChatGroq:
        return ChatGroq(
            model_name=spec.name,
            groq_api_key=self._api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
            max_retries=0,  # the gateway decides what to retry
            http_client=self.http_client,
        )

    def _structured_reply(self, output: Any) -> ChatReply:
        if not isinstance(output, dict):
            return ChatReply(parsed=output if isinstance(output, BaseModel) else None)
        raw = output.get("raw")
        parsed = output.get("parsed")
        error = output.get("parsing_error")
        if error is not None or not isinstance(parsed, BaseModel):
            raise StructuredOutputInvalid(f"{type(error).__name__}: {str(error)[:300]}")
        return ChatReply(
            message=raw,
            usage=usage_from_message(raw) if raw is not None else None,
            headers=self.last_headers(),
            parsed=parsed,
        )

    def _wrap_stream(
        self, chunks: Iterator[AIMessage], reply: ChatReply, spec: ModelSpec
    ) -> Iterator[AIMessageChunk]:
        try:
            for chunk in chunks:
                yield as_chunk(chunk)
        except LLMError:
            raise
        except Exception as exc:
            raise classify_exception(exc, provider=self.name, model=spec.name) from exc
        finally:
            reply.headers.update(self.last_headers())

    def _capture_headers(self, response: httpx.Response) -> None:
        self._local.headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower().startswith(_HEADER_PREFIXES)
        }

    def last_headers(self) -> dict[str, str]:
        headers = getattr(self._local, "headers", None)
        return dict(headers) if headers else {}


@lru_cache(maxsize=4)
def groq_provider(api_key: str) -> GroqProvider:
    """One provider (and HTTP connection pool) per key for the life of the process."""
    return GroqProvider(api_key)
