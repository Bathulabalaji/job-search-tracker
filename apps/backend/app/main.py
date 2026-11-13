import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import AuthError, ConflictError, NotFoundError, RateLimitedError
from app.core.logging import configure_logging
from app.llm.errors import LLMError

logger = logging.getLogger("app")


def create_app() -> FastAPI:
    settings = get_settings()  # also validates security settings, failing fast on a bad config
    configure_logging()
    app = FastAPI(title=settings.app_name, version="0.2.0")

    # Cookies need credentialed CORS, which forbids wildcards: origins and headers are explicit.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Authorization", "X-Client-Type"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if "/auth/" in request.url.path or request.url.path.endswith("/auth"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(NotFoundError)
    def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc), "code": "not_found"})

    @app.exception_handler(ConflictError)
    def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc), "code": "conflict"})

    @app.exception_handler(AuthError)
    def _auth_error(_: Request, exc: AuthError) -> JSONResponse:
        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.retry_after_seconds)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
            headers=headers,
        )

    @app.exception_handler(LLMError)
    def _llm_error(request: Request, exc: LLMError) -> JSONResponse:
        # Provider details stay in the log; the client gets a stable code and a plain message.
        logger.warning(
            "assistant error",
            extra={
                "code": exc.code,
                "provider": exc.provider,
                "model": exc.model,
                "detail": exc.detail[:300],
                "path": request.url.path,
            },
        )
        headers: dict[str, str] = {}
        if exc.retry_after is not None:
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.user_message, "code": exc.code},
            headers=headers,
        )

    @app.exception_handler(Exception)
    def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Details go to the log only; the client never sees internals.
        logger.error(
            "unhandled error",
            exc_info=exc,
            extra={"path": request.url.path, "method": request.method},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong. Please try again.", "code": "internal_error"},
        )

    app.include_router(api_router)
    return app


app = create_app()
