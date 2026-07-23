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


def _prod_settings(**overrides):
    from app.core.config import Settings

    base = dict(
        app_env="production", jwt_secret="x" * 40, pii_hash_salt="y" * 40,
        use_supabase=True, supabase_connection_string="postgresql://x/y",
        cors_origins="https://bluntly.ph",
    )
    base.update(overrides)
    return Settings(**base)


def test_production_refuses_the_console_provider():
    """console only logs codes — in production every OTP would silently vanish."""
    issues = " ".join(_prod_settings(email_provider="console").production_issues())
    assert "EMAIL_PROVIDER=console" in issues


def test_production_refuses_resend_without_a_key():
    issues = " ".join(
        _prod_settings(email_provider="resend", resend_api_key="").production_issues())
    assert "RESEND_API_KEY" in issues


def test_production_refuses_the_shared_resend_sender():
    """onboarding@resend.dev can only reach the Resend account owner (403)."""
    issues = " ".join(_prod_settings(
        email_provider="resend", resend_api_key="re_x",
        email_from="onboarding@resend.dev").production_issues())
    assert "resend.dev" in issues


def test_production_accepts_a_verified_sender():
    issues = " ".join(_prod_settings(
        email_provider="resend", resend_api_key="re_x",
        email_from="no-reply@bluntly.ph").production_issues())
    assert "EMAIL_PROVIDER" not in issues and "RESEND_API_KEY" not in issues


def test_production_refuses_localhost_cors():
    """A production browser origin would be refused by a localhost allowlist."""
    issues = " ".join(_prod_settings(
        email_provider="resend", resend_api_key="re_x",
        email_from="no-reply@bluntly.ph",
        cors_origins="http://localhost:3000").production_issues())
    assert "CORS_ORIGINS" in issues


def test_production_refuses_localhost_redis():
    """No Redis means enforce_rate_limit fails open and brute-force protection
    on login/register silently disappears (core/rate_limit.py)."""
    issues = " ".join(_prod_settings(
        email_provider="resend", resend_api_key="re_x",
        email_from="no-reply@bluntly.ph",
        redis_url="redis://localhost:6379/0").production_issues())
    assert "REDIS_URL" in issues


def test_production_clean_config_has_no_issues():
    issues = _prod_settings(
        email_provider="resend", resend_api_key="re_x",
        email_from="no-reply@bluntly.ph",
        cors_origins="https://bluntly.ph",
        redis_url="rediss://cache.internal:6379/0").production_issues()
    assert issues == [], issues
