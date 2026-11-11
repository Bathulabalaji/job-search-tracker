from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import (
    COMMON_PASSWORDS,
    MAX_PASSWORD_LENGTH,
    constant_time_equals,
    csrf_token_for,
    generate_token,
    hash_identifier,
    hash_password,
    hash_token,
    make_signed_nonce,
    password_problems,
    verify_password,
    verify_signed_nonce,
)

SECRET = "unit-test-secret-key-that-is-long-enough"
NOW = datetime(2026, 11, 11, 4, 30, tzinfo=UTC)


class TestPasswordHashing:
    def test_hash_is_argon2id_and_never_the_plain_text(self) -> None:
        hashed = hash_password("Correct-Horse-9")
        assert hashed.startswith("$argon2id$")
        assert "Correct-Horse-9" not in hashed

    def test_same_password_hashes_differently_each_time(self) -> None:
        assert hash_password("Correct-Horse-9") != hash_password("Correct-Horse-9")

    def test_verify(self) -> None:
        hashed = hash_password("Correct-Horse-9")
        assert verify_password("Correct-Horse-9", hashed) is True
        assert verify_password("correct-horse-9", hashed) is False

    def test_missing_or_corrupt_hash_never_verifies(self) -> None:
        assert verify_password("anything", None) is False
        assert verify_password("anything", "not-a-hash") is False


class TestTokens:
    def test_tokens_are_long_and_unique(self) -> None:
        tokens = {generate_token() for _ in range(50)}
        assert len(tokens) == 50
        assert all(len(t) >= 43 for t in tokens)  # 256 bits, url-safe base64

    def test_hash_is_stable_and_hides_the_token(self) -> None:
        token = generate_token()
        assert hash_token(token) == hash_token(token)
        assert token not in hash_token(token)
        assert len(hash_token(token)) == 64

    def test_identifier_hash_ignores_case_and_whitespace(self) -> None:
        assert hash_identifier(" Alice@Example.com ") == hash_identifier("alice@example.com")

    def test_constant_time_equals(self) -> None:
        assert constant_time_equals("abc", "abc")
        assert not constant_time_equals("abc", "abd")
        assert not constant_time_equals("abc", "abcd")


class TestCsrf:
    def test_bound_to_the_session_token(self) -> None:
        assert csrf_token_for("session-a", SECRET) == csrf_token_for("session-a", SECRET)
        assert csrf_token_for("session-a", SECRET) != csrf_token_for("session-b", SECRET)

    def test_depends_on_the_server_secret(self) -> None:
        assert csrf_token_for("session-a", SECRET) != csrf_token_for("session-a", SECRET + "x")


class TestNonce:
    def test_fresh_nonce_verifies(self) -> None:
        nonce = make_signed_nonce(NOW, SECRET)
        assert verify_signed_nonce(nonce, NOW + timedelta(seconds=30), SECRET, 600)

    def test_expires(self) -> None:
        nonce = make_signed_nonce(NOW, SECRET)
        assert not verify_signed_nonce(nonce, NOW + timedelta(seconds=601), SECRET, 600)

    def test_rejects_tampering_and_other_secrets(self) -> None:
        nonce = make_signed_nonce(NOW, SECRET)
        issued, rand, sig = nonce.split(".")
        assert not verify_signed_nonce(f"{int(issued) + 1}.{rand}.{sig}", NOW, SECRET, 600)
        assert not verify_signed_nonce(f"{issued}.{rand}x.{sig}", NOW, SECRET, 600)
        assert not verify_signed_nonce(nonce, NOW, "a-different-secret-that-is-long-enough", 600)

    @pytest.mark.parametrize("bad", ["", "a.b", "a.b.c.d", "x.y.z"])
    def test_rejects_malformed(self, bad: str) -> None:
        assert not verify_signed_nonce(bad, NOW, SECRET, 600)

    def test_rejects_issue_time_in_the_future(self) -> None:
        nonce = make_signed_nonce(NOW + timedelta(hours=1), SECRET)
        assert not verify_signed_nonce(nonce, NOW, SECRET, 600)


class TestPasswordPolicy:
    def test_accepts_a_reasonable_password(self) -> None:
        assert password_problems("Correct-Horse-9", email="a@b.co", full_name="Jo Doe") == []

    @pytest.mark.parametrize(
        ("password", "fragment"),
        [
            ("Sh0rt", "at least"),
            ("allletterspassword", "number"),
            ("12345678901234", "letter"),
            ("x" * (MAX_PASSWORD_LENGTH + 1) + "1", "at most"),
        ],
    )
    def test_rejects(self, password: str, fragment: str) -> None:
        assert any(fragment in p for p in password_problems(password))

    def test_rejects_common_passwords(self) -> None:
        common = next(p for p in COMMON_PASSWORDS if len(p) >= 10 and any(c.isdigit() for c in p))
        assert any("common" in p for p in password_problems(common.upper()))

    def test_rejects_passwords_built_from_email_or_name(self) -> None:
        assert any("email" in p for p in password_problems("alice-secret-9", email="alice@x.io"))
        assert any(
            "name" in p for p in password_problems("Walker-secret-9", full_name="Alice Walker")
        )

    def test_short_name_parts_are_not_policed(self) -> None:
        assert password_problems("Correct-Horse-9", full_name="Jo Li") == []
