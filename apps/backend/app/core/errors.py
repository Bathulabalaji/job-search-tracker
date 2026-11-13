class DomainError(Exception):
    """Base class for errors the API maps to HTTP responses."""


class NotFoundError(DomainError):
    def __init__(self, entity: str, entity_id: int) -> None:
        super().__init__(f"{entity} {entity_id} not found")


class ConflictError(DomainError):
    pass


class AuthError(DomainError):
    """An authentication or account problem that is safe to show to the user.

    `code` is a stable machine-readable string the frontend branches on.
    """

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class RateLimitedError(AuthError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            "rate_limited",
            "Too many attempts. Please wait a while and try again.",
            status_code=429,
        )
        self.retry_after_seconds = max(retry_after_seconds, 1)


class ChatError(AuthError):
    """A chat request the user can act on (busy conversation, unknown run...). Same mapping
    as AuthError: {"detail", "code"} with the given status."""


class ChatQuotaError(RateLimitedError):
    def __init__(self, retry_after_seconds: int, message: str) -> None:
        super().__init__(retry_after_seconds)
        self.code = "chat_quota"
        self.message = message
