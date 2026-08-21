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
        # Pinned, not inherited. `Settings` reads the ambient environment, so
        # these tests were quietly describing whatever pool the *runner* had
        # configured: the CI database job sets DB_POOL_SIZE=2 to stay under the
        # session pooler's client cap, and that alone made
        # `test_production_clean_config_has_no_issues` fail on a threadpool
        # check that has nothing to do with email. A test that asserts "a clean
        # production config has no issues" has to define what clean means.
        db_pool_size=10, db_max_overflow=10, threadpool_tokens=20,
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




def test_production_accepts_the_shared_resend_sender():
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


def test_production_warns_about_localhost_redis_but_still_boots():
    """This used to be a refusal, and the reason expired.

    No Redis once meant `enforce_rate_limit` failed open and brute-force
    protection on login silently disappeared, so refusing to boot was right.
    Migration 0028 gave the limiter a Postgres fallback — verified enforcing
    against production, where ten failed logins answer 401 and the eleventh
    answers 429 with Redis still unconfigured.

    Keeping the refusal would have been actively harmful rather than merely
    out of date: every production check is gated on APP_ENV, so a refusal over
    a solved problem keeps the CORS, PII-salt and postback-secret checks
    switched off as well.
    """
    settings = _prod_settings(
        email_provider="resend", resend_api_key="re_x",
        email_from="no-reply@bluntly.ph",
        redis_url="redis://localhost:6379/0")
    assert "REDIS_URL" not in " ".join(settings.production_issues())
    assert "REDIS_URL" in " ".join(settings.production_warnings())


def test_production_clean_config_has_no_issues():
    issues = _prod_settings(
        email_provider="resend", resend_api_key="re_x",
        email_from="no-reply@bluntly.ph",
        cors_origins="https://bluntly.ph",
        redis_url="rediss://cache.internal:6379/0").production_issues()
    assert issues == [], issues
