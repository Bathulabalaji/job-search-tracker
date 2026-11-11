import json
import logging

import httpx
import pytest

from app.core.config import Settings
from app.emails import build_email_sender
from app.emails.mailer import AuthMailer
from app.emails.render import render_email
from app.emails.sender import (
    EmailDeliveryError,
    EmailMessage,
    SendGridSender,
    SuppressedSender,
)
from app.models.user import User
from tests.conftest import FakeEmailSender

API_KEY = "SG.super-secret-api-key-value"


def _message() -> EmailMessage:
    return EmailMessage(
        to_email="alice@example.com",
        to_name="Alice",
        subject="Hello",
        html="<p>Hi</p>",
        text="Hi",
        kind="verify_email",
    )


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class TestTemplates:
    def _render(self, **overrides: object) -> tuple[str, str]:
        params: dict[str, object] = {
            "app_name": "Career Command Center",
            "subject": "Verify",
            "preheader": "Confirm your email",
            "heading": "Welcome",
            "paragraphs": ["Please confirm."],
            "button_label": "Verify",
            "button_url": "https://app.example/verify-email#token=abc",
            "footnote": "Ignore if not you.",
        }
        params.update(overrides)
        return render_email(**params)  # type: ignore[arg-type]

    def test_html_is_responsive_and_branded(self) -> None:
        html, text = self._render()
        assert 'name="viewport"' in html
        assert "@media (max-width: 620px)" in html
        assert "Career Command Center" in html
        assert 'href="https://app.example/verify-email#token=abc"' in html
        assert "https://app.example/verify-email#token=abc" in text  # plain-text alternative

    def test_user_supplied_values_are_escaped(self) -> None:
        html, _ = self._render(
            heading="<script>alert(1)</script>",
            paragraphs=['<img src=x onerror="steal()">'],
            button_url='https://x.example/"><script>bad()</script>',
        )
        assert "<script>" not in html
        assert "onerror=" not in html.replace("&quot;", "") or "&lt;img" in html
        assert "&lt;script&gt;" in html

    def test_no_button_when_there_is_no_link(self) -> None:
        html, text = self._render(button_label=None, button_url=None)
        assert 'class="button"' not in html
        assert "http" not in text


class TestMailer:
    def _user(self) -> User:
        return User(email="alice@example.com", full_name="Alice <b>Walker</b>")

    def test_verification_email_content_and_link(self, settings: Settings) -> None:
        sender = FakeEmailSender()
        AuthMailer(sender, settings).send_verification(self._user(), "tok-123_abc")
        message = sender.messages[0]
        assert message.kind == "verify_email"
        assert message.to_email == "alice@example.com"
        assert "http://localhost:5173/verify-email#token=tok-123_abc" in message.html
        assert "24 hours" in message.text

    def test_the_link_always_uses_the_configured_frontend_url(self, settings: Settings) -> None:
        sender = FakeEmailSender()
        custom = settings.model_copy(update={"frontend_url": "https://tracker.example.com/"})
        AuthMailer(sender, custom).send_password_reset(self._user(), "tok")
        assert "https://tracker.example.com/reset-password#token=tok" in sender.messages[0].text
        assert "30 minutes" in sender.messages[0].text

    def test_html_in_a_name_is_escaped(self, settings: Settings) -> None:
        sender = FakeEmailSender()
        AuthMailer(sender, settings).send_password_changed(self._user())
        assert "<b>Walker</b>" not in sender.messages[0].html

    def test_delivery_failures_are_swallowed_and_logged_without_secrets(
        self, settings: Settings, caplog: pytest.LogCaptureFixture
    ) -> None:
        sender = FakeEmailSender()
        sender.fail_with = EmailDeliveryError("SendGrid returned HTTP 401")
        with caplog.at_level(logging.ERROR, logger="app.email"):
            AuthMailer(sender, settings).send_verification(self._user(), "tok-secret-value")
        logged = " ".join(str(r.__dict__) + r.getMessage() for r in caplog.records)
        assert "email delivery failed" in logged
        assert "tok-secret-value" not in logged

    def test_unexpected_errors_never_escape(self, settings: Settings) -> None:
        sender = FakeEmailSender()
        sender.fail_with = RuntimeError("boom")
        AuthMailer(sender, settings).send_verification(self._user(), "tok")  # must not raise


class TestSendGridSender:
    def _sender(self) -> SendGridSender:
        return SendGridSender(
            api_key=API_KEY, from_address="no-reply@example.com", from_name="Tracker"
        )

    def test_request_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        def fake_post(url: str, **kwargs: object) -> _Response:
            captured.update(url=url, **kwargs)
            return _Response(202)

        monkeypatch.setattr(httpx, "post", fake_post)
        self._sender().send(_message())

        assert captured["url"] == "https://api.sendgrid.com/v3/mail/send"
        assert captured["headers"] == {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }
        payload = captured["json"]
        assert isinstance(payload, dict)
        assert payload["from"] == {"email": "no-reply@example.com", "name": "Tracker"}
        assert payload["personalizations"][0]["to"][0]["email"] == "alice@example.com"
        assert {c["type"] for c in payload["content"]} == {"text/plain", "text/html"}
        # Single-use links must not be rewritten through a click-tracking redirect.
        assert payload["tracking_settings"]["click_tracking"]["enable"] is False
        json.dumps(payload)  # serialisable

    def test_retries_once_on_a_server_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        responses = iter([_Response(503), _Response(202)])
        monkeypatch.setattr(httpx, "post", lambda *a, **k: next(responses))
        self._sender().send(_message())  # second attempt succeeds

    def test_does_not_retry_a_client_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[int] = []

        def fake_post(*args: object, **kwargs: object) -> _Response:
            calls.append(1)
            return _Response(401)

        monkeypatch.setattr(httpx, "post", fake_post)
        with pytest.raises(EmailDeliveryError, match="401"):
            self._sender().send(_message())
        assert len(calls) == 1

    def test_network_errors_become_delivery_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(*args: object, **kwargs: object) -> _Response:
            raise httpx.ConnectTimeout("timed out")

        monkeypatch.setattr(httpx, "post", fake_post)
        with pytest.raises(EmailDeliveryError):
            self._sender().send(_message())

    def test_the_api_key_never_appears_in_repr_or_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sender = self._sender()
        assert API_KEY not in repr(sender)
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _Response(400))
        with pytest.raises(EmailDeliveryError) as info:
            sender.send(_message())
        assert API_KEY not in str(info.value)


class TestSenderSelection:
    def test_sendgrid_when_fully_configured(self, settings: Settings) -> None:
        configured = settings.model_copy(
            update={"sendgrid_api_key": API_KEY, "email_from_address": "no-reply@example.com"}
        )
        assert isinstance(build_email_sender(configured), SendGridSender)

    @pytest.mark.parametrize(
        "update",
        [{}, {"sendgrid_api_key": API_KEY}, {"email_from_address": "no-reply@example.com"}],
    )
    def test_suppressed_when_incomplete(self, settings: Settings, update: dict[str, str]) -> None:
        assert isinstance(build_email_sender(settings.model_copy(update=update)), SuppressedSender)

    def test_suppressed_sender_logs_the_kind_but_not_the_message(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        message = _message()
        with caplog.at_level(logging.WARNING, logger="app.email"):
            SuppressedSender().send(message)
        logged = " ".join(str(r.__dict__) for r in caplog.records)
        assert "verify_email" in logged
        assert "alice@example.com" not in logged
