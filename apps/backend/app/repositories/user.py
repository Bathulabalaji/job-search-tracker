from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.auth import AuthIdentity, AuthToken, RateLimitEvent, UserSession
from app.models.enums import AuthProvider, AuthTokenPurpose
from app.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user


class AuthIdentityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_subject(self, provider: AuthProvider, subject: str) -> AuthIdentity | None:
        return self.session.scalar(
            select(AuthIdentity)
            .where(AuthIdentity.provider == provider)
            .where(AuthIdentity.subject == subject)
        )

    def exists_for_user(self, user_id: int, provider: AuthProvider) -> bool:
        stmt = (
            select(AuthIdentity.id)
            .where(AuthIdentity.user_id == user_id)
            .where(AuthIdentity.provider == provider)
        )
        return self.session.scalar(stmt) is not None

    def add(self, identity: AuthIdentity) -> AuthIdentity:
        self.session.add(identity)
        self.session.flush()
        return identity


class AuthTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, token: AuthToken) -> AuthToken:
        self.session.add(token)
        self.session.flush()
        return token

    def get_by_hash(self, token_hash: str, purpose: AuthTokenPurpose) -> AuthToken | None:
        return self.session.scalar(
            select(AuthToken)
            .where(AuthToken.token_hash == token_hash)
            .where(AuthToken.purpose == purpose)
        )

    def consume(self, token_id: int, now: datetime) -> bool:
        """Mark a token used. Atomic: of two concurrent requests, only one gets True."""
        result = self.session.execute(
            update(AuthToken)
            .where(AuthToken.id == token_id)
            .where(AuthToken.used_at.is_(None))
            .where(AuthToken.expires_at > now)
            .values(used_at=now)
            .returning(AuthToken.id)
        )
        return result.first() is not None

    def invalidate_for_user(self, user_id: int, purpose: AuthTokenPurpose, now: datetime) -> None:
        self.session.execute(
            update(AuthToken)
            .where(AuthToken.user_id == user_id)
            .where(AuthToken.purpose == purpose)
            .where(AuthToken.used_at.is_(None))
            .values(used_at=now)
        )


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        self.session.flush()
        return user_session

    def get_by_hash(self, token_hash: str) -> UserSession | None:
        return self.session.scalar(select(UserSession).where(UserSession.token_hash == token_hash))

    def revoke(self, session_id: int, now: datetime) -> None:
        self.session.execute(
            update(UserSession)
            .where(UserSession.id == session_id)
            .where(UserSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    def revoke_all_for_user(
        self, user_id: int, now: datetime, except_session_id: int | None = None
    ) -> None:
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id)
            .where(UserSession.revoked_at.is_(None))
        )
        if except_session_id is not None:
            stmt = stmt.where(UserSession.id != except_session_id)
        self.session.execute(stmt.values(revoked_at=now))


class RateLimitRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def window_stats(self, bucket: str, since: datetime) -> tuple[int, datetime | None]:
        row = self.session.execute(
            select(func.count(), func.min(RateLimitEvent.created_at))
            .where(RateLimitEvent.bucket == bucket)
            .where(RateLimitEvent.created_at > since)
        ).one()
        return int(row[0]), row[1]

    def add(self, bucket: str, now: datetime) -> None:
        self.session.add(RateLimitEvent(bucket=bucket, created_at=now))
        self.session.flush()

    def clear(self, bucket: str) -> None:
        self.session.query(RateLimitEvent).filter(RateLimitEvent.bucket == bucket).delete()

    def purge_older_than(self, bucket: str, cutoff: datetime) -> None:
        self.session.query(RateLimitEvent).filter(
            RateLimitEvent.bucket == bucket, RateLimitEvent.created_at <= cutoff
        ).delete()
