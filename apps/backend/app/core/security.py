"""Password hashing, token generation and CSRF tokens. No database access here."""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# argon2id with the library's recommended defaults. Tests swap in cheap parameters.
_hasher = PasswordHasher()
_dummy_hash: str | None = None


def set_hasher_for_tests(hasher: PasswordHasher) -> None:
    global _hasher, _dummy_hash
    _hasher = hasher
    _dummy_hash = None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time: verifies against a dummy hash when there is no real one."""
    global _dummy_hash
    if password_hash is None:
        if _dummy_hash is None:
            _dummy_hash = _hasher.hash(secrets.token_urlsafe(16))
        try:
            _hasher.verify(_dummy_hash, password)
        except (VerificationError, InvalidHashError):
            pass
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# ---- Tokens ------------------------------------------------------------------------------------


def generate_token() -> str:
    """256 bits of randomness, URL-safe. Only its hash is ever stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 is enough for high-entropy random tokens (no salting or stretching needed)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_identifier(value: str) -> str:
    """Short stable hash for rate-limit buckets and logs, so raw emails are not stored there."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:24]


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# ---- CSRF and nonces -----------------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def csrf_token_for(session_token: str, secret_key: str) -> str:
    """Bound to the session: an attacker who cannot read the session cookie cannot derive it."""
    digest = hmac.new(
        secret_key.encode("utf-8"), b"csrf:" + session_token.encode("utf-8"), hashlib.sha256
    ).digest()
    return _b64(digest)


def make_signed_nonce(now: datetime, secret_key: str) -> str:
    """`<unix-ts>.<random>.<signature>`: proves the server issued it recently, no storage."""
    payload = f"{int(now.timestamp())}.{secrets.token_urlsafe(16)}"
    signature = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return f"{payload}.{_b64(signature.digest())}"


def verify_signed_nonce(nonce: str, now: datetime, secret_key: str, max_age_seconds: int) -> bool:
    parts = nonce.split(".")
    if len(parts) != 3:
        return False
    payload = f"{parts[0]}.{parts[1]}"
    expected = _b64(
        hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    )
    if not constant_time_equals(parts[2], expected):
        return False
    try:
        issued = int(parts[0])
    except ValueError:
        return False
    age = now.timestamp() - issued
    return 0 <= age <= max_age_seconds


# ---- Password policy -----------------------------------------------------------------------------

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128
# A short deny-list of the passwords people actually pick; length rules catch most of the rest.
COMMON_PASSWORDS = frozenset(
    {
        "password", "password1", "password123", "passw0rd", "123456789", "1234567890",
        "qwertyuiop", "qwerty123", "iloveyou1", "welcome123", "admin12345", "letmein123",
        "abc123456", "111111111", "changeme123", "trustno1234", "career1234",
    }
)  # fmt: skip


def password_problems(password: str, *, email: str = "", full_name: str = "") -> list[str]:
    """Human-readable reasons a password is rejected (empty list = acceptable)."""
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"Use at most {MAX_PASSWORD_LENGTH} characters.")
    if not re.search(r"[A-Za-z]", password):
        problems.append("Include at least one letter.")
    if not re.search(r"\d", password):
        problems.append("Include at least one number.")
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS:
        problems.append("That password is too common.")
    local_part = email.split("@")[0].lower() if email else ""
    if len(local_part) >= 4 and local_part in lowered:
        problems.append("Do not include your email name in the password.")
    for part in full_name.lower().split():
        if len(part) >= 4 and part in lowered:
            problems.append("Do not include your name in the password.")
            break
    return problems
