"""Everything that can go wrong when talking to an AI provider, in a form the API can show.

Provider SDK exceptions never leave `app.llm`: the adapters translate them into these classes.
Each has a stable `code` that clients branch on and a `user_message` that is safe to display;
`detail` is for logs only and may contain provider text.
"""


def _about(seconds: int | None) -> str:
    if seconds is None or seconds <= 90:
        return "a minute"
    return f"{-(-seconds // 60)} minutes"  # ceil


class LLMError(Exception):
    code: str = "assistant_unavailable"
    status_code: int = 503
    retryable: bool = True
    default_message: str = "The AI provider is having trouble. Please try again in a minute."

    def __init__(
        self,
        detail: str = "",
        *,
        provider: str | None = None,
        model: str | None = None,
        retry_after: int | None = None,
        user_message: str | None = None,
    ) -> None:
        super().__init__(detail or self.default_message)
        self.detail = detail
        self.provider = provider
        self.model = model
        self.retry_after = max(retry_after, 1) if retry_after is not None else None
        self.user_message = user_message or self.default_message

    def __repr__(self) -> str:
        name = type(self).__name__
        return f"{name}(code={self.code!r}, model={self.model!r}, detail={self.detail!r})"


class RateLimited(LLMError):
    """The provider refused this call for now (429). `kind` says whether a per-minute or a
    per-day budget ran out; the gateway treats those very differently."""

    code = "assistant_busy"
    status_code = 429

    def __init__(
        self,
        detail: str = "",
        *,
        kind: str = "minute",
        headers: dict[str, str] | None = None,
        provider: str | None = None,
        model: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(detail, provider=provider, model=model, retry_after=retry_after)
        self.kind = kind
        self.headers = headers or {}


class ContextTooLong(LLMError):
    code = "assistant_context_too_long"
    status_code = 400
    retryable = False
    default_message = (
        "This conversation has grown too long for me to keep in view. Start a new chat to continue."
    )


class ProviderUnavailable(LLMError):
    """5xx, timeouts and connection failures: usually transient. `kind` is for the usage log."""

    code = "assistant_unavailable"
    status_code = 503

    def __init__(
        self,
        detail: str = "",
        *,
        kind: str = "error",
        provider: str | None = None,
        model: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(detail, provider=provider, model=model, retry_after=retry_after)
        self.kind = kind  # error | timeout | connection


class ProviderBadRequest(LLMError):
    """We sent something the provider rejected (a tool schema it dislikes, an unsupported
    parameter). Not the user's fault, so the message stays generic and the detail is logged."""

    code = "assistant_bad_request"
    status_code = 400
    retryable = False


class ProviderAuthFailed(LLMError):
    """Wrong or revoked API key. An operator problem: users see the generic message."""

    code = "assistant_misconfigured"
    status_code = 503
    retryable = False


class ContentBlocked(LLMError):
    code = "assistant_content_blocked"
    status_code = 400
    retryable = False
    default_message = "The AI provider declined to answer that. Try rephrasing your message."


class StructuredOutputInvalid(LLMError):
    """The model answered, but not with JSON that matches the requested schema."""

    code = "assistant_bad_output"
    status_code = 503


class AllModelsExhausted(LLMError):
    """No model in the policy has budget left right now."""

    code = "assistant_capacity"
    status_code = 429

    def __init__(
        self,
        detail: str = "",
        *,
        provider: str | None = None,
        model: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(detail, provider=provider, model=model, retry_after=retry_after)
        self.user_message = (
            "I'm at capacity right now (free-tier limits). Try again in about "
            f"{_about(self.retry_after)} and I'll pick up where I left off."
        )


class CapacityExceeded(AllModelsExhausted):
    """Too many model switches in one run: every candidate failed in turn, so stop rather
    than keep hammering providers."""


class RunTimedOut(LLMError):
    code = "assistant_timeout"
    status_code = 504
    default_message = "That took too long. Please try again."


class EmbeddingUnavailable(LLMError):
    """Embeddings have one model and no fallback: callers persist a 'pending' state and retry."""

    code = "embedding_unavailable"
    status_code = 503
    default_message = "Indexing is paused for now (free-tier limit) and will retry automatically."


class AssistantDisabled(LLMError):
    code = "assistant_disabled"
    status_code = 503
    retryable = False
    default_message = "The assistant is not enabled on this server."
