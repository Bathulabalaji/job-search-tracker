from fastapi.testclient import TestClient

from app.services.google_auth import GoogleClaims
from tests.auth_helpers import API, Response
from tests.conftest import FakeGoogleVerifier


def claims(
    *,
    sub: str = "google-sub-1",
    email: str = "gina@example.com",
    verified: bool = True,
    name: str | None = "Gina Google",
    nonce: str | None = None,
) -> GoogleClaims:
    return GoogleClaims(subject=sub, email=email, email_verified=verified, name=name, nonce=nonce)


def get_nonce(client: TestClient) -> str:
    nonce = client.get(f"{API}/auth/google/nonce").json()["nonce"]
    assert isinstance(nonce, str)
    return nonce


def google_login(
    client: TestClient,
    google: FakeGoogleVerifier,
    *,
    nonce: str | None = None,
    token_nonce: str | None = None,
    sub: str = "google-sub-1",
    email: str = "gina@example.com",
    verified: bool = True,
    name: str | None = "Gina Google",
) -> Response:
    """Run the Google sign-in the way the browser does. `token_nonce` simulates a mismatch."""
    issued = nonce if nonce is not None else get_nonce(client)
    google.claims = claims(
        sub=sub,
        email=email,
        verified=verified,
        name=name,
        nonce=token_nonce if token_nonce is not None else issued,
    )
    return client.post(
        f"{API}/auth/google", json={"credential": "google-id-token-" + "x" * 20, "nonce": issued}
    )


def sign_in_with_google(
    client: TestClient,
    google: FakeGoogleVerifier,
    *,
    sub: str = "google-sub-1",
    email: str = "gina@example.com",
    name: str | None = "Gina Google",
) -> dict[str, str]:
    response = google_login(client, google, sub=sub, email=email, name=name)
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}
