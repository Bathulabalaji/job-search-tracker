import secrets
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Career Command Center"
    environment: str = "local"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/career_command_center"
    )
    cors_origins: list[str] = [
        "http://localhost:5173",
        "https://job-search-tracker-blond.vercel.app",
    ]

    # Timezone used to decide what "today" and "working day" mean.
    timezone: str = "Asia/Kolkata"
    # Auto-rules from the brief.
    followup_working_days: int = 2
    ghost_after_days: int = 21

    # ---- Authentication ----------------------------------------------------------------------
    # Public URL of the React app. Email links point here; it is never taken from a request.
    frontend_url: str = "http://localhost:5173"
    # Signs CSRF tokens. Required (32+ chars) unless the frontend runs on localhost.
    secret_key: str = ""

    # Session cookie. `cookie_secure=None` means "secure unless the frontend is on localhost".
    cookie_name: str = "session"
    cookie_secure: bool | None = None
    # Use "none" only when the frontend and API are on different sites AND browsers allow
    # third-party cookies. A same-origin proxy (see README) is the more reliable option.
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    session_ttl_days: int = 30  # absolute lifetime
    session_idle_days: int = 7  # signed out after this long without use
    email_verification_ttl_hours: int = 24
    password_reset_ttl_minutes: int = 30

    # Google Sign-In. The client ID is public; no client secret is needed for ID-token sign-in.
    google_client_id: str = ""
    # Extra OAuth client IDs whose ID tokens we accept: the iOS and Android app clients.
    # Comma-separated. Native apps get tokens minted for their own client, not the web one.
    google_extra_client_ids: str = ""

    # SendGrid. With no API key, emails are suppressed (and a warning is logged without the link).
    sendgrid_api_key: str = ""
    email_from_address: str = ""
    email_from_name: str = "Career Command Center"
    email_reply_to: str = ""

    # Local development helpers. Refused unless the frontend runs on localhost.
    auto_verify_email: bool = False

    # Unclaimed pre-accounts data goes to this email's account once it is verified. When empty,
    # the first account to verify claims it. SET THIS IN PRODUCTION.
    legacy_data_owner_email: str = ""

    # How many reverse proxies sit in front of the API (0 = trust nothing, use the socket IP).
    trusted_proxy_count: int = 0

    # ---- AI assistant ---------------------------------------------------------------------
    # Free-tier LLM providers. With neither key set the assistant is disabled (endpoints 503).
    groq_api_key: str = ""
    google_ai_api_key: str = ""
    # Per-model budgets as JSON (see app/llm/catalog.py). Match what your provider console shows.
    llm_model_limits: str = ""
    # Task -> ordered model list as JSON, replacing the built-in routing (app/llm/policy.py).
    llm_policy_override: str = ""
    llm_request_timeout_seconds: float = 30.0  # one provider call
    llm_run_timeout_seconds: float = 90.0  # one gateway call including fallbacks
    llm_max_model_switches: int = 3  # per run, before giving up with a capacity error
    llm_circuit_failures: int = 3  # consecutive failures that open a model's circuit
    llm_circuit_cooldown_seconds: int = 60
    chat_daily_messages: int = 60  # per user
    chat_per_minute: int = 6  # per user
    chat_max_conversations: int = 50  # per user
    embedding_model: str = "gemini-embedding-001"
    embedding_dims: int = 768

    @property
    def frontend_is_local(self) -> bool:
        return (urlparse(self.frontend_url).hostname or "") in LOCAL_HOSTS

    @property
    def effective_cookie_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return not self.frontend_is_local

    @property
    def google_audiences(self) -> list[str]:
        """Every Google client ID an ID token may have been issued to (web first)."""
        extras = [c.strip() for c in self.google_extra_client_ids.split(",")]
        return [c for c in [self.google_client_id.strip(), *extras] if c]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key or self.google_ai_api_key)

    @property
    def allowed_origins(self) -> set[str]:
        """Origins allowed to make state-changing requests (CORS list plus the frontend URL)."""
        parsed = urlparse(self.frontend_url)
        frontend = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
        return {o.rstrip("/") for o in self.cors_origins} | ({frontend} if frontend else set())

    @model_validator(mode="after")
    def _validate_security(self) -> "Settings":
        if not self.secret_key:
            if not self.frontend_is_local:
                raise ValueError(
                    "SECRET_KEY must be set (32+ random characters) when FRONTEND_URL is not "
                    "localhost. Generate one with: python -c 'import secrets; "
                    "print(secrets.token_urlsafe(48))'"
                )
            # Local only: an ephemeral key. Sessions survive restarts; CSRF tokens are re-issued.
            self.secret_key = secrets.token_urlsafe(48)
        elif len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        if self.cookie_samesite == "none" and not self.effective_cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none requires secure cookies (COOKIE_SECURE=true)")
        if self.auto_verify_email and not self.frontend_is_local:
            raise ValueError("AUTO_VERIFY_EMAIL is only allowed when FRONTEND_URL is localhost")
        if not self.frontend_is_local and not self.frontend_url.startswith("https://"):
            raise ValueError("FRONTEND_URL must use https:// outside local development")
        return self

    @model_validator(mode="after")
    def _validate_assistant(self) -> "Settings":
        # Fail at startup, not on the first chat message, when the JSON overrides are broken.
        from app.llm.catalog import load_catalog
        from app.llm.policy import load_policy

        load_policy(self.llm_policy_override, load_catalog(self.llm_model_limits))
        if self.embedding_dims <= 0:
            raise ValueError("EMBEDDING_DIMS must be positive")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
