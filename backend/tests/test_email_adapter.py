"""Email adapter — provider switching and failure modes.

No test here may reach the network: the suite pins EMAIL_PROVIDER=console in
conftest, and the resend paths are exercised only for their guard clauses.
"""

from __future__ import annotations

import pytest

from app.adapters import email as email_adapter
from app.core.config import settings


@pytest.fixture(autouse=True)
def _restore_provider():
    """Each test mutates global settings; put them back."""
    provider, key = settings.email_provider, settings.resend_api_key
    yield
    settings.email_provider, settings.resend_api_key = provider, key


def test_console_provider_logs_the_code(caplog):
    settings.email_provider = "console"
    with caplog.at_level("INFO", logger="adapters.email"):
        email_adapter.send_otp_email("someone@example.com", "123456")
    # The code travels in structured extras, not the message body.
    codes = [getattr(r, "extra_fields", {}).get("code") for r in caplog.records]
    assert "123456" in codes


def test_resend_provider_without_key_raises():
    settings.email_provider = "resend"
    settings.resend_api_key = ""
    with pytest.raises(email_adapter.EmailNotConfigured):
        email_adapter.send_otp_email("someone@example.com", "123456")


def test_unknown_provider_raises():
    settings.email_provider = "carrier-pigeon"
    with pytest.raises(email_adapter.EmailNotConfigured):
        email_adapter.send_otp_email("someone@example.com", "123456")


def test_provider_failure_does_not_leak_the_code(monkeypatch):
    """A 4xx from Resend must not put the plaintext code in the exception."""
    settings.email_provider = "resend"
    settings.resend_api_key = "re_test_key"

    class _Resp:
        status_code = 422
        text = "domain not verified"

    monkeypatch.setattr(email_adapter.httpx, "post", lambda *a, **k: _Resp())
    with pytest.raises(email_adapter.EmailSendError) as exc:
        email_adapter.send_otp_email("someone@example.com", "123456")
    assert "123456" not in str(exc.value)
