"""Google AI Studio (Gemini) through LangChain's `ChatGoogleGenerativeAI` and
`GoogleGenerativeAIEmbeddings`. Google sends no rate-limit headers; its 429 bodies carry a
RetryInfo that `classify_exception` turns into `retry_after`."""

from collections.abc import Iterator, Sequence
from functools import lru_cache
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, SecretStr

from app.llm.catalog import ModelSpec
from app.llm.errors import ContentBlocked, LLMError, StructuredOutputInvalid
from app.llm.providers.base import (
    ChatReply,
    EmbedKind,
    ToolLike,
    as_chunk,
    message_content_text,
    usage_from_message,
)
from app.llm.providers.classify import classify_exception

_BLOCKED_FINISH_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION", "SPII"}
_TASK_TYPES: dict[EmbedKind, str] = {
    "document": "RETRIEVAL_DOCUMENT",
    "query": "RETRIEVAL_QUERY",
}


class GoogleProvider:
    name = "google"

    def __init__(self, api_key: str) -> None:
        self._api_key = SecretStr(api_key)

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
        model = self._model(spec, timeout=timeout, max_tokens=max_tokens, temperature=temperature)
        inputs = list(messages)
        try:
            if schema is not None:
                structured = model.with_structured_output(schema, include_raw=True)
                return self._structured_reply(structured.invoke(inputs))
            runnable = model.bind_tools(list(tools)) if tools else model
            if stream:
                return ChatReply(chunks=self._wrap_stream(runnable.stream(inputs), spec))
            message = runnable.invoke(inputs)
            self._check_blocked(message)
            return ChatReply(message=message, usage=usage_from_message(message))
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
        embeddings = self._embeddings(spec, timeout=timeout)
        try:
            return embeddings.embed_documents(
                list(texts), task_type=_TASK_TYPES[kind], output_dimensionality=dims
            )
        except Exception as exc:
            raise classify_exception(exc, provider=self.name, model=spec.name) from exc

    # ---- internals ------------------------------------------------------------------------

    def _model(
        self, spec: ModelSpec, *, timeout: float, max_tokens: int, temperature: float
    ) -> ChatGoogleGenerativeAI:
        # Gemini 3.x uses fixed sampling defaults (and warns when given a temperature), and
        # thinks before answering unless told not to: low effort keeps chat responsive.
        sampling: dict[str, Any] = (
            {"reasoning_effort": "low"}
            if spec.name.startswith("gemini-3")
            else {"temperature": temperature}
        )
        return ChatGoogleGenerativeAI(
            model=spec.name,
            api_key=self._api_key,
            max_output_tokens=max_tokens,
            timeout=timeout,
            max_retries=0,  # the gateway decides what to retry
            **sampling,
        )

    def _embeddings(self, spec: ModelSpec, *, timeout: float) -> GoogleGenerativeAIEmbeddings:
        name = spec.name if spec.name.startswith("models/") else f"models/{spec.name}"
        return GoogleGenerativeAIEmbeddings(
            model=name, api_key=self._api_key, request_options={"timeout": timeout}
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
            message=raw, usage=usage_from_message(raw) if raw is not None else None, parsed=parsed
        )

    def _wrap_stream(
        self, chunks: Iterator[AIMessage], spec: ModelSpec
    ) -> Iterator[AIMessageChunk]:
        try:
            for message in chunks:
                chunk = as_chunk(message)
                self._check_blocked(chunk)
                yield chunk
        except LLMError:
            raise
        except Exception as exc:
            raise classify_exception(exc, provider=self.name, model=spec.name) from exc

    @staticmethod
    def _check_blocked(message: AIMessage | AIMessageChunk) -> None:
        reason = str(message.response_metadata.get("finish_reason", "")).upper()
        if reason in _BLOCKED_FINISH_REASONS and not message_content_text(message):
            raise ContentBlocked(f"finish_reason={reason}")


@lru_cache(maxsize=4)
def google_provider(api_key: str) -> GoogleProvider:
    return GoogleProvider(api_key)
