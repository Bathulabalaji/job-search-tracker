import re
from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.security import MAX_PASSWORD_LENGTH
from app.models.enums import UserStatus

# Deliberately conservative: one @, a dot in the domain, no spaces. Real validation is the
# verification email itself.
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not _EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address")
    return email


Email = Annotated[str, StringConstraints(max_length=320)]
# Passwords are never trimmed or altered. Length is capped so Argon2 is not fed megabytes.
Password = Annotated[str, Field(min_length=1, max_length=MAX_PASSWORD_LENGTH + 64, repr=False)]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class RegisterRequest(_Request):
    full_name: str = Field(min_length=1, max_length=100)
    email: Email
    password: Password
    accept_terms: bool

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        name = " ".join(value.split())
        if not name or _CONTROL_CHARS.search(value):
            raise ValueError("Enter your full name")
        return name

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return _normalize_email(value)

    @model_validator(mode="after")
    def _terms(self) -> Self:
        if not self.accept_terms:
            raise ValueError("You must accept the terms to create an account")
        return self


class LoginRequest(_Request):
    email: Email
    password: Password

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return _normalize_email(value)


class EmailOnlyRequest(_Request):
    email: Email

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return _normalize_email(value)


class TokenRequest(_Request):
    token: str = Field(min_length=10, max_length=200)


class ResetPasswordRequest(_Request):
    token: str = Field(min_length=10, max_length=200)
    password: Password


class ChangePasswordRequest(_Request):
    current_password: Password
    new_password: Password


class UpdateProfileRequest(_Request):
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        name = " ".join(value.split())
        if not name or _CONTROL_CHARS.search(value):
            raise ValueError("Enter your full name")
        return name


class GoogleLoginRequest(_Request):
    credential: str = Field(min_length=20, max_length=4096)
    nonce: str = Field(min_length=10, max_length=200)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    status: UserStatus
    email_verified: bool
    has_password: bool
    google_linked: bool
    created_at: datetime
    last_login_at: datetime | None


class AuthResponse(BaseModel):
    user: UserRead
    # Send this back in the X-CSRF-Token header on every POST/PATCH/PUT/DELETE.
    csrf_token: str
    is_new_user: bool = False
    # Only sent to native apps (X-Client-Type: mobile), which keep it in the device's secure
    # storage. Browsers never receive it: their session lives in an HttpOnly cookie.
    session_token: str | None = None


class MessageResponse(BaseModel):
    message: str


class NonceResponse(BaseModel):
    nonce: str
