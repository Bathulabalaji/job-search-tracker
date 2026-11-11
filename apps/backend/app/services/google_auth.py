from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from google.auth.exceptions import GoogleAuthError as GoogleLibError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleAuthError(Exception):
    """The Google credential could not be verified. The message is for logs, not users."""


@dataclass(frozen=True)
class GoogleClaims:
    subject: str
    email: str
    email_verified: bool
    name: str | None
    nonce: str | None


class GoogleTokenVerifier(Protocol):
    def verify(self, credential: str) -> GoogleClaims: ...


class GoogleIdTokenVerifier:
    """Verifies a Google ID token: signature (Google's published keys), issuer, audience, expiry.

    Nothing from the browser is trusted except the signed token itself.
    """

    def __init__(self, client_id: str, extra_client_ids: Sequence[str] = ()) -> None:
        self.client_id = client_id
        self.audiences = [c for c in (client_id, *extra_client_ids) if c]

    def verify(self, credential: str) -> GoogleClaims:
        if not self.audiences:
            raise GoogleAuthError("GOOGLE_CLIENT_ID is not configured")
        try:
            info = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                credential,
                google_requests.Request(),
                # Rejects tokens minted for any app that is not ours (web, iOS or Android).
                audience=self.audiences[0] if len(self.audiences) == 1 else self.audiences,
                clock_skew_in_seconds=10,
            )
        except (ValueError, GoogleLibError) as exc:
            raise GoogleAuthError(f"token rejected: {exc}") from exc

        if info.get("iss") not in GOOGLE_ISSUERS:
            raise GoogleAuthError("unexpected issuer")
        subject = info.get("sub")
        email = info.get("email")
        if not isinstance(subject, str) or not subject or not isinstance(email, str) or not email:
            raise GoogleAuthError("token has no subject or email")
        verified = info.get("email_verified")
        # Google sends a boolean, but older tokens carried the strings "true"/"false".
        email_verified = verified is True or (isinstance(verified, str) and verified == "true")
        name = info.get("name")
        nonce = info.get("nonce")
        return GoogleClaims(
            subject=subject,
            email=email.strip().lower(),
            email_verified=email_verified,
            name=name if isinstance(name, str) else None,
            nonce=nonce if isinstance(nonce, str) else None,
        )
