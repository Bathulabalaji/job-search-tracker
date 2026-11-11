"""Authentication emails: what each message says, and how its link is built."""

import logging
from datetime import timedelta
from urllib.parse import quote

from fastapi import BackgroundTasks

from app.core.config import Settings
from app.emails.render import render_email
from app.emails.sender import EmailDeliveryError, EmailMessage, EmailSender
from app.models.user import User

logger = logging.getLogger("app.email")


def _first_name(user: User) -> str:
    return user.full_name.split()[0] if user.full_name.strip() else "there"


def _humanize(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    if minutes >= 120 and minutes % 60 == 0:
        return f"{minutes // 60} hours"
    return f"{minutes} minutes"


class AuthMailer:
    """Builds and sends account emails. With `background`, delivery happens after the response,
    so a slow or failing mail provider never changes how fast (or whether) an endpoint answers."""

    def __init__(
        self,
        sender: EmailSender,
        settings: Settings,
        background: BackgroundTasks | None = None,
    ) -> None:
        self.sender = sender
        self.settings = settings
        self.background = background

    # -- public ------------------------------------------------------------------------------

    def send_verification(self, user: User, token: str) -> None:
        # The token travels in the URL fragment: browsers never send it to servers or Referer.
        url = f"{self._base()}/verify-email#token={quote(token)}"
        ttl = _humanize(timedelta(hours=self.settings.email_verification_ttl_hours))
        self._send(
            user,
            kind="verify_email",
            subject=f"Verify your email for {self.settings.app_name}",
            preheader="Confirm your email address to finish creating your account.",
            heading=f"Welcome, {_first_name(user)}!",
            paragraphs=[
                f"Thanks for signing up for {self.settings.app_name}. "
                "Please confirm your email address to activate your account.",
                f"This link works for {ttl} and can only be used once.",
            ],
            button_label="Verify email address",
            button_url=url,
            footnote="If you did not create an account, you can ignore this email.",
        )

    def send_password_reset(self, user: User, token: str) -> None:
        url = f"{self._base()}/reset-password#token={quote(token)}"
        ttl = _humanize(timedelta(minutes=self.settings.password_reset_ttl_minutes))
        self._send(
            user,
            kind="reset_password",
            subject=f"Reset your {self.settings.app_name} password",
            preheader="Use this link to choose a new password.",
            heading="Reset your password",
            paragraphs=[
                f"Hi {_first_name(user)}, we received a request to reset the password for "
                "your account.",
                f"This link works for {ttl} and can only be used once.",
            ],
            button_label="Choose a new password",
            button_url=url,
            footnote="If you did not request this, you can ignore this email. "
            "Your password will not change.",
        )

    def send_password_changed(self, user: User) -> None:
        self._send(
            user,
            kind="password_changed",
            subject=f"Your {self.settings.app_name} password was changed",
            preheader="A security notice about your account.",
            heading="Your password was changed",
            paragraphs=[
                f"Hi {_first_name(user)}, the password for your account was just changed, "
                "and you were signed out of your other devices.",
                "If this was you, there is nothing more to do. If it was not, reset your "
                "password straight away.",
            ],
            button_label="Reset password",
            button_url=f"{self._base()}/forgot-password",
            footnote="If you did not make this change, someone else may have access to your email.",
        )

    # -- internals ---------------------------------------------------------------------------

    def _base(self) -> str:
        return self.settings.frontend_url.rstrip("/")

    def _send(
        self,
        user: User,
        *,
        kind: str,
        subject: str,
        preheader: str,
        heading: str,
        paragraphs: list[str],
        button_label: str | None,
        button_url: str | None,
        footnote: str,
    ) -> None:
        html_body, text_body = render_email(
            app_name=self.settings.app_name,
            subject=subject,
            preheader=preheader,
            heading=heading,
            paragraphs=paragraphs,
            button_label=button_label,
            button_url=button_url,
            footnote=footnote,
        )
        message = EmailMessage(
            to_email=user.email,
            to_name=user.full_name,
            subject=subject,
            html=html_body,
            text=text_body,
            kind=kind,
        )
        if self.background is not None:
            self.background.add_task(self._deliver, message)
        else:
            self._deliver(message)

    def _deliver(self, message: EmailMessage) -> None:
        try:
            self.sender.send(message)
        except EmailDeliveryError as exc:
            # Log the kind and the failure only: never the recipient's link or the API key.
            logger.error("email delivery failed", extra={"kind": message.kind, "error": str(exc)})
        except Exception:
            logger.exception("unexpected email error", extra={"kind": message.kind})
