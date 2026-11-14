"""Input hygiene shared by new schemas: control characters, links and email addresses.

Postgres text cannot hold a NUL byte (it answers 500), and anything the user types may end up
in a link or an email, so these are cleaned or refused at the edge, with a clear message.
"""

import re
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, BeforeValidator

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EMAIL = re.compile(r"^[^\s@<>()\[\],;:\\\"]+@[^\s@<>()\[\],;:\\\"]+\.[^\s@<>()\[\],;:\\\"]{2,}$")


def strip_controls(value: object) -> object:
    """Remove control characters (keeping newlines and tabs) and trim the ends."""
    if isinstance(value, str):
        return _CONTROL.sub("", value).strip()
    return value


def _http_url(value: str) -> str:
    if not value:
        return value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc or " " in value:
        raise ValueError("Enter a full link starting with http:// or https://")
    return value


def _email(value: str) -> str:
    if not value:
        return value
    if not _EMAIL.match(value):
        raise ValueError("Enter a valid email address")
    return value


def _single_line(value: str) -> str:
    return " ".join(value.split())


CleanText = Annotated[str, BeforeValidator(strip_controls)]
OneLine = Annotated[str, BeforeValidator(strip_controls), AfterValidator(_single_line)]
HttpLink = Annotated[str, BeforeValidator(strip_controls), AfterValidator(_http_url)]
EmailAddress = Annotated[str, BeforeValidator(strip_controls), AfterValidator(_email)]
