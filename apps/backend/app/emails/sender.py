import logging
from dataclasses import dataclass, field
from typing import Protocol

import httpx

logger = logging.getLogger("app.email")

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


@dataclass(frozen=True)
class EmailMessage:
    to_email: str
    to_name: str
    subject: str
    html: str
    text: str
    kind: str  # for logging only, e.g. "verify_email"


class EmailDeliveryError(Exception):
    pass


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


@dataclass
class SendGridSender:
    api_key: str = field(repr=False)  # never printed or logged
    from_address: str
    from_name: str
    reply_to: str = ""
    timeout_seconds: float = 10.0

    def send(self, message: EmailMessage) -> None:
        payload: dict[str, object] = {
            "personalizations": [
                {"to": [{"email": message.to_email, "name": message.to_name}]},
            ],
            "from": {"email": self.from_address, "name": self.from_name},
            "subject": message.subject,
            "content": [
                {"type": "text/plain", "value": message.text},
                {"type": "text/html", "value": message.html},
            ],
            # Links in these emails are single-use secrets: do not rewrite them for click tracking.
            "tracking_settings": {"click_tracking": {"enable": False, "enable_text": False}},
        }
        if self.reply_to:
            payload["reply_to"] = {"email": self.reply_to}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        last_error: Exception | None = None
        for _ in range(2):  # one retry for transient failures
            try:
                response = httpx.post(
                    SENDGRID_URL, json=payload, headers=headers, timeout=self.timeout_seconds
                )
            except httpx.HTTPError as exc:
                last_error = exc
                continue
            if response.status_code < 300:
                return
            last_error = EmailDeliveryError(f"SendGrid returned HTTP {response.status_code}")
            if response.status_code < 500 and response.status_code != 429:
                break  # a client error will not fix itself on retry
        raise EmailDeliveryError(str(last_error)) from last_error


class SuppressedSender:
    """Used when SendGrid is not configured. Never logs the body (it holds a secret link)."""

    def send(self, message: EmailMessage) -> None:
        logger.warning(
            "email suppressed: SENDGRID_API_KEY / EMAIL_FROM_ADDRESS are not configured",
            extra={"kind": message.kind},
        )
