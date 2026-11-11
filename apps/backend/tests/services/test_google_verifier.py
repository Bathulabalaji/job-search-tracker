import pytest
from google.auth.exceptions import TransportError
from google.oauth2 import id_token

from app.services.google_auth import GoogleAuthError, GoogleIdTokenVerifier

CLIENT_ID = "my-app.apps.googleusercontent.com"


def _claims(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "Gina@Example.com",
        "email_verified": True,
        "name": "Gina G",
        "nonce": "abc",
    }
    base.update(overrides)
    return base


@pytest.fixture
def fake_google(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Replace the network/crypto call; we test OUR handling of its result and errors."""
    state: dict[str, object] = {"result": _claims(), "seen": None}

    def fake_verify(
        token: str, request: object, audience: str | None = None, **kwargs: object
    ) -> dict[str, object]:
        state["seen"] = {"token": token, "audience": audience}
        result = state["result"]
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, dict)
        return result

    monkeypatch.setattr(id_token, "verify_oauth2_token", fake_verify)
    return state


def test_a_valid_token_becomes_normalised_claims(fake_google: dict[str, object]) -> None:
    claims = GoogleIdTokenVerifier(CLIENT_ID).verify("the-token")
    assert claims.subject == "1234567890"
    assert claims.email == "gina@example.com"
    assert claims.email_verified is True
    assert claims.nonce == "abc"


def test_the_audience_is_always_our_client_id(fake_google: dict[str, object]) -> None:
    GoogleIdTokenVerifier(CLIENT_ID).verify("the-token")
    assert fake_google["seen"] == {"token": "the-token", "audience": CLIENT_ID}


def test_nothing_is_verified_when_google_is_not_configured() -> None:
    with pytest.raises(GoogleAuthError, match="not configured"):
        GoogleIdTokenVerifier("").verify("the-token")


@pytest.mark.parametrize(
    "error",
    [
        ValueError("Token expired"),
        ValueError("Could not verify token signature."),
        ValueError("Token has wrong audience other-app, expected my-app"),
        TransportError("could not fetch certs"),  # type: ignore[no-untyped-call]
    ],
)
def test_library_rejections_become_google_auth_errors(
    fake_google: dict[str, object], error: Exception
) -> None:
    fake_google["result"] = error
    with pytest.raises(GoogleAuthError):
        GoogleIdTokenVerifier(CLIENT_ID).verify("the-token")


@pytest.mark.parametrize(
    "issuer", ["https://evil.example", "accounts.google.com.evil.example", None]
)
def test_a_wrong_issuer_is_refused(fake_google: dict[str, object], issuer: str | None) -> None:
    fake_google["result"] = _claims(iss=issuer)
    with pytest.raises(GoogleAuthError, match="issuer"):
        GoogleIdTokenVerifier(CLIENT_ID).verify("the-token")


@pytest.mark.parametrize("issuer", ["accounts.google.com", "https://accounts.google.com"])
def test_both_google_issuer_spellings_are_accepted(
    fake_google: dict[str, object], issuer: str
) -> None:
    fake_google["result"] = _claims(iss=issuer)
    assert GoogleIdTokenVerifier(CLIENT_ID).verify("t").subject == "1234567890"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(True, True), (False, False), ("true", True), ("false", False), (None, False), ("yes", False)],
)
def test_email_verified_is_read_strictly(
    fake_google: dict[str, object], raw: object, expected: bool
) -> None:
    fake_google["result"] = _claims(email_verified=raw)
    assert GoogleIdTokenVerifier(CLIENT_ID).verify("t").email_verified is expected


@pytest.mark.parametrize("missing", ["sub", "email"])
def test_tokens_without_a_subject_or_email_are_refused(
    fake_google: dict[str, object], missing: str
) -> None:
    claims = _claims()
    del claims[missing]
    fake_google["result"] = claims
    with pytest.raises(GoogleAuthError):
        GoogleIdTokenVerifier(CLIENT_ID).verify("t")


def test_tokens_for_any_configured_app_client_are_accepted(
    fake_google: dict[str, object],
) -> None:
    GoogleIdTokenVerifier(CLIENT_ID, ["ios.apps.googleusercontent.com"]).verify("t")
    assert fake_google["seen"] == {
        "token": "t",
        "audience": [CLIENT_ID, "ios.apps.googleusercontent.com"],
    }
