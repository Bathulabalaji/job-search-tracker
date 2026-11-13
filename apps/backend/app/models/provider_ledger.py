from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProviderUsageEvent(Base):
    """One row per call to an external AI provider. Append-only: feeds usage and cost reports."""

    __tablename__ = "provider_usage_events"
    __table_args__ = (
        Index("ix_provider_usage_events_resource_created", "resource", "created_at"),
        Index("ix_provider_usage_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20))  # llm | embedding | search
    provider: Mapped[str] = mapped_column(String(32))
    resource: Mapped[str] = mapped_column(String(100))  # model name, or a provider endpoint
    task: Mapped[str] = mapped_column(String(40))
    prompt_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    latency_ms: Mapped[int] = mapped_column(default=0, server_default="0")
    # ok | rate_limited | quota | error | timeout | blocked | bad_request
    outcome: Mapped[str] = mapped_column(String(20))
    error_code: Mapped[str | None] = mapped_column(String(64))
    run_id: Mapped[str | None] = mapped_column(String(64))


class ProviderResourceState(Base):
    """Budget state for one model: rolling counters, what the provider last reported, cooldowns
    and the circuit breaker. One row per resource, shared by every worker (like rate limits)."""

    __tablename__ = "provider_resource_state"

    resource: Mapped[str] = mapped_column(String(100), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))

    minute_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    minute_requests: Mapped[int] = mapped_column(default=0, server_default="0")
    minute_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    day_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    day_requests: Mapped[int] = mapped_column(default=0, server_default="0")
    day_tokens: Mapped[int] = mapped_column(default=0, server_default="0")

    # From rate-limit headers (Groq sends them on every response). Authoritative while fresh.
    reported_remaining_requests: Mapped[int | None]
    reported_remaining_tokens: Mapped[int | None]
    reported_requests_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reported_tokens_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cooldown_reason: Mapped[str | None] = mapped_column(String(40))
    consecutive_failures: Mapped[int] = mapped_column(default=0, server_default="0")
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    circuit_state: Mapped[str] = mapped_column(
        String(10), default="closed", server_default="closed"
    )  # closed | open | half_open
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
