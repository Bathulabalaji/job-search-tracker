from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.security import generate_token, hash_token
from app.models.auth import UserSession
from app.models.enums import UserStatus
from app.models.user import User
from app.repositories.user import SessionRepository, UserRepository

# Avoid a database write on every request: slide the idle window at most this often.
TOUCH_INTERVAL = timedelta(minutes=5)


class SessionService:
    """Server-side sessions. The cookie carries a random token; only its hash is stored, so a
    database leak cannot be replayed, and signing out really does invalidate the session."""

    def __init__(self, session: Session, clock: Clock, settings: Settings) -> None:
        self.clock = clock
        self.settings = settings
        self.sessions = SessionRepository(session)
        self.users = UserRepository(session)

    def create(self, user: User, user_agent: str | None) -> str:
        """Start a session and return the raw token for the cookie (never stored)."""
        now = self.clock.now()
        token = generate_token()
        self.sessions.add(
            UserSession(
                user_id=user.id,
                token_hash=hash_token(token),
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(days=self.settings.session_ttl_days),
                user_agent=(user_agent or "")[:255] or None,
            )
        )
        return token

    def resolve(self, token: str) -> tuple[User, UserSession] | None:
        """The user behind a cookie token, or None if it is unknown, expired, revoked or the
        account is no longer allowed to sign in."""
        record = self.sessions.get_by_hash(hash_token(token))
        if record is None or record.revoked_at is not None:
            return None
        now = self.clock.now()
        idle_limit = record.last_seen_at + timedelta(days=self.settings.session_idle_days)
        if record.expires_at <= now or idle_limit <= now:
            return None
        user = self.users.get(record.user_id)
        # Re-checked on every request so suspending an account takes effect immediately.
        if user is None or user.status != UserStatus.active or not user.email_verified:
            return None
        if now - record.last_seen_at > TOUCH_INTERVAL:
            record.last_seen_at = now
        return user, record

    def revoke(self, session_id: int) -> None:
        self.sessions.revoke(session_id, self.clock.now())

    def revoke_all(self, user_id: int, except_session_id: int | None = None) -> None:
        self.sessions.revoke_all_for_user(user_id, self.clock.now(), except_session_id)
