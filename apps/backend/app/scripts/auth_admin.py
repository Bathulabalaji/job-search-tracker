"""Operator tool for accounts: `uv run python -m app.scripts.auth_admin <command> ...`

This is the only place that can print a one-time sign-in link, and only against a local
frontend, so there is never a log line or API response that exposes one.
"""

import argparse
import getpass
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.core.security import hash_password, password_problems
from app.db.session import SessionLocal
from app.emails.mailer import AuthMailer
from app.emails.sender import SuppressedSender
from app.models.enums import AuthTokenPurpose, UserStatus
from app.models.user import User
from app.services.auth import AuthService
from app.services.google_auth import GoogleIdTokenVerifier


def _service(session: Session, settings: Settings) -> AuthService:
    clock = Clock(tz=ZoneInfo(settings.timezone))
    mailer = AuthMailer(SuppressedSender(), settings)
    return AuthService(session, clock, settings, mailer, GoogleIdTokenVerifier(""))


def _user(session: Session, email: str) -> User:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise SystemExit(f"No account for {email}")
    return user


def create_user(session: Session, settings: Settings, args: argparse.Namespace) -> None:
    email = args.email.strip().lower()
    if session.scalar(select(User).where(User.email == email)) is not None:
        raise SystemExit(f"An account for {email} already exists")
    password = getpass.getpass("Password (hidden): ")
    problems = password_problems(password, email=email, full_name=args.name)
    if problems:
        raise SystemExit("Password rejected: " + " ".join(problems))
    clock = Clock(tz=ZoneInfo(settings.timezone))
    user = User(
        email=email,
        full_name=args.name,
        password_hash=hash_password(password),
        status=UserStatus.active,
        terms_accepted_at=clock.now(),
        password_changed_at=clock.now(),
    )
    session.add(user)
    session.flush()
    _service(session, settings)._mark_verified(user)  # noqa: SLF001 - also claims old data
    session.commit()
    print(f"Created verified account {email} (id {user.id}).")


def verify_email(session: Session, settings: Settings, args: argparse.Namespace) -> None:
    user = _user(session, args.email)
    _service(session, settings)._mark_verified(user)  # noqa: SLF001
    session.commit()
    print(f"{user.email} is verified.")


def set_status(session: Session, settings: Settings, args: argparse.Namespace) -> None:
    user = _user(session, args.email)
    user.status = UserStatus.suspended if args.command == "suspend" else UserStatus.active
    if user.status == UserStatus.suspended:
        _service(session, settings).sessions.revoke_all(user.id)  # sign them out everywhere
    session.commit()
    print(f"{user.email} is now {user.status.value}.")


def issue_link(session: Session, settings: Settings, args: argparse.Namespace) -> None:
    if not settings.frontend_is_local:
        raise SystemExit("issue-link only works when FRONTEND_URL is localhost.")
    user = _user(session, args.email)
    service = _service(session, settings)
    purpose = (
        AuthTokenPurpose.verify_email if args.kind == "verify" else AuthTokenPurpose.reset_password
    )
    ttl = timedelta(hours=1)
    token = service._create_token(user, purpose, ttl)  # noqa: SLF001
    session.commit()
    path = "verify-email" if args.kind == "verify" else "reset-password"
    print(f"{settings.frontend_url.rstrip('/')}/{path}#token={token}")
    print("(valid for 1 hour, single use)")


def list_users(session: Session, settings: Settings, args: argparse.Namespace) -> None:
    del settings, args
    for user in session.scalars(select(User).order_by(User.id)):
        flags = [user.status.value, "verified" if user.email_verified else "unverified"]
        print(f"{user.id:>4}  {user.email:<40} {', '.join(flags)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-user", help="Create a verified account (password via hidden prompt)")
    p.add_argument("email")
    p.add_argument("--name", required=True)
    for name in ("verify-email", "suspend", "activate"):
        sub.add_parser(name).add_argument("email")
    p = sub.add_parser("issue-link", help="Print a one-time verify/reset link (local only)")
    p.add_argument("kind", choices=["verify", "reset"])
    p.add_argument("email")
    sub.add_parser("list-users")
    args = parser.parse_args()

    handlers = {
        "create-user": create_user,
        "verify-email": verify_email,
        "suspend": set_status,
        "activate": set_status,
        "issue-link": issue_link,
        "list-users": list_users,
    }
    settings = get_settings()
    with SessionLocal() as session:
        handlers[args.command](session, settings, args)


if __name__ == "__main__":
    main()
