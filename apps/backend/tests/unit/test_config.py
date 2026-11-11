import pytest
from pydantic import ValidationError

from app.core.config import Settings

GOOD_SECRET = "x" * 40


def make(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


class TestLocalDevelopment:
    def test_works_with_no_secrets_configured(self) -> None:
        settings = make()
        assert settings.frontend_is_local
        assert len(settings.secret_key) >= 32  # an ephemeral key was generated
        assert (
            settings.effective_cookie_secure is False
        )  # http://localhost cannot set Secure cookies

    def test_the_ephemeral_key_differs_per_process_start(self) -> None:
        assert make().secret_key != make().secret_key

    def test_auto_verify_is_allowed_locally(self) -> None:
        assert make(auto_verify_email=True).auto_verify_email


class TestProduction:
    PROD = {"frontend_url": "https://tracker.example.com", "secret_key": GOOD_SECRET}

    def test_a_valid_production_config(self) -> None:
        settings = make(**self.PROD)
        assert settings.effective_cookie_secure is True
        assert "https://tracker.example.com" in settings.allowed_origins

    def test_a_missing_secret_key_stops_the_app_from_starting(self) -> None:
        with pytest.raises(ValidationError, match="SECRET_KEY must be set"):
            make(frontend_url="https://tracker.example.com")

    def test_a_short_secret_key_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="at least 32"):
            make(frontend_url="https://tracker.example.com", secret_key="short")

    def test_plain_http_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="https://"):
            make(frontend_url="http://tracker.example.com", secret_key=GOOD_SECRET)

    def test_auto_verify_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="AUTO_VERIFY_EMAIL"):
            make(**self.PROD, auto_verify_email=True)

    def test_secure_cookies_can_be_forced_off_only_explicitly(self) -> None:
        assert make(**self.PROD, cookie_secure=False).effective_cookie_secure is False

    def test_a_trailing_slash_in_origins_is_ignored(self) -> None:
        settings = make(**self.PROD, cors_origins=["https://other.example.com/"])
        assert "https://other.example.com" in settings.allowed_origins


class TestSameSite:
    def test_none_requires_secure_cookies(self) -> None:
        with pytest.raises(ValidationError, match="requires secure cookies"):
            make(cookie_samesite="none")  # local frontend => cookies are not Secure

    def test_none_is_fine_with_secure_cookies(self) -> None:
        settings = make(
            frontend_url="https://tracker.example.com",
            secret_key=GOOD_SECRET,
            cookie_samesite="none",
        )
        assert settings.cookie_samesite == "none"
        assert settings.effective_cookie_secure is True

    def test_unknown_values_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make(cookie_samesite="sometimes")


def test_google_audiences_lists_web_then_extra_clients() -> None:
    s = Settings(
        google_client_id="web", google_extra_client_ids=" ios , android,, ", _env_file=None
    )
    assert s.google_audiences == ["web", "ios", "android"]
    assert Settings(_env_file=None).google_audiences == []
