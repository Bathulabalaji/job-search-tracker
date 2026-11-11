from dataclasses import dataclass
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.core.errors import AuthError
from app.core.security import constant_time_equals, csrf_token_for
from app.db.session import get_db
from app.emails import build_email_sender
from app.emails.mailer import AuthMailer
from app.emails.sender import EmailSender
from app.models.auth import UserSession
from app.models.user import User
from app.services.auth import AuthService
from app.services.google_auth import GoogleIdTokenVerifier, GoogleTokenVerifier
from app.services.sessions import SessionService

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSRF_HEADER = "x-csrf-token"

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSession = Annotated[Session, Depends(get_db)]


def get_clock(settings: SettingsDep) -> Clock:
    return Clock(tz=ZoneInfo(settings.timezone))


ClockDep = Annotated[Clock, Depends(get_clock)]


def client_ip(request: Request, settings: Settings) -> str:
    """The caller's IP. X-Forwarded-For is only believed when we are told how many proxies
    sit in front of us, and then only the entry those proxies appended (it cannot be forged)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [h.strip() for h in forwarded.split(",") if h.strip()]
    if settings.trusted_proxy_count > 0 and len(hops) >= settings.trusted_proxy_count:
        return hops[-settings.trusted_proxy_count]
    return request.client.host if request.client else "unknown"


def get_client_ip(request: Request, settings: SettingsDep) -> str:
    return client_ip(request, settings)


ClientIp = Annotated[str, Depends(get_client_ip)]


def require_trusted_origin(request: Request, settings: SettingsDep) -> None:
    """Reject state-changing browser requests that come from some other website.

    Browsers always send Origin on cross-origin POST/PUT/PATCH/DELETE. Non-browser clients
    (curl, tests) send none and are let through; they are not a CSRF vector.
    """
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") not in settings.allowed_origins:
        raise AuthError("bad_origin", "Request origin is not allowed.", 403)


# ---- Providers (overridden in tests) ----------------------------------------------------------


def get_email_sender(settings: SettingsDep) -> EmailSender:
    return build_email_sender(settings)


def get_google_verifier(settings: SettingsDep) -> GoogleTokenVerifier:
    return GoogleIdTokenVerifier(settings.google_client_id)


def get_mailer(
    background: BackgroundTasks,
    settings: SettingsDep,
    sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> AuthMailer:
    return AuthMailer(sender, settings, background)


def get_auth_service(
    db: DbSession,
    clock: ClockDep,
    settings: SettingsDep,
    mailer: Annotated[AuthMailer, Depends(get_mailer)],
    google: Annotated[GoogleTokenVerifier, Depends(get_google_verifier)],
) -> AuthService:
    return AuthService(db, clock, settings, mailer, google)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# ---- Current user -------------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: UserSession
    csrf_token: str


def _resolve(request: Request, db: Session, clock: Clock, settings: Settings) -> AuthContext | None:
    raw = request.cookies.get(settings.cookie_name)
    if not raw:
        return None
    resolved = SessionService(db, clock, settings).resolve(raw)
    if resolved is None:
        return None
    user, record = resolved
    expected = csrf_token_for(raw, settings.secret_key)
    if request.method not in SAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not supplied or not constant_time_equals(supplied, expected):
            raise AuthError(
                "csrf_failed", "Security check failed. Please refresh and try again.", 403
            )
    db.commit()  # persists the sliding idle timeout if it moved
    return AuthContext(user=user, session=record, csrf_token=expected)


def get_optional_auth(
    request: Request, db: DbSession, clock: ClockDep, settings: SettingsDep
) -> AuthContext | None:
    return _resolve(request, db, clock, settings)


def get_auth_context(
    request: Request, db: DbSession, clock: ClockDep, settings: SettingsDep
) -> AuthContext:
    context = _resolve(request, db, clock, settings)
    if context is None:
        raise AuthError("not_authenticated", "Please sign in to continue.", 401)
    return context


AuthContextDep = Annotated[AuthContext, Depends(get_auth_context)]
OptionalAuthDep = Annotated[AuthContext | None, Depends(get_optional_auth)]


def get_current_user(context: AuthContextDep) -> User:
    return context.user


CurrentUser = Annotated[User, Depends(get_current_user)]
