"""Integration boundaries must fail as controlled errors, never as raw 500s.

The PayPal audit found three faults escaping the caller's handler - a timeout,
a 200 without the expected key, and a malformed body. That class turned out to
be productive, so these pin the same properties for the other adapters, plus
the rule that an upstream body never reaches an exception message.

Why that rule: these strings reach logs. Resend echoes the recipient address
back, and otp_service already logs that address separately - so including the
body duplicated PII into the log on every failed send. Lazada's requests are
signed with app_key and a signature, and an error response can quote request
context back.
"""

from __future__ import annotations

import httpx
import pytest

from app.adapters import email as email_adapter
from app.adapters import lazada


def _configure_lazada(monkeypatch):
    from app.core.config import settings
    for key, value in (("lazada_app_key", "ak"), ("lazada_app_secret", "as"),
                       ("lazada_user_token", "ut"),
                       ("lazada_api_base", "https://api.example.test/rest")):
        monkeypatch.setattr(settings, key, value, raising=False)


class _Resp:
    def __init__(self, status=200, payload=None, text="", raises=False):
        self.status_code = status
        self._payload = payload
        self.text = text
        self._raises = raises

    def json(self):
        if self._raises:
            raise ValueError("not json")
        return self._payload


# --------------------------------------------------------------------------
# Lazada
# --------------------------------------------------------------------------

def test_lazada_transport_failure_is_a_lazada_error(monkeypatch):
    _configure_lazada(monkeypatch)
    monkeypatch.setattr(lazada.httpx, "get",
                        lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    with pytest.raises(lazada.LazadaError):
        lazada._call("/x", {})


def test_lazada_non_json_200_is_a_lazada_error(monkeypatch):
    """Previously raised JSONDecodeError, which callers do not catch."""
    _configure_lazada(monkeypatch)
    monkeypatch.setattr(lazada.httpx, "get", lambda *a, **k: _Resp(raises=True))
    with pytest.raises(lazada.LazadaError) as exc:
        lazada._call("/x", {})
    assert "non-json" in str(exc.value).lower()


def test_lazada_http_error_does_not_echo_the_body(monkeypatch):
    _configure_lazada(monkeypatch)
    secret_ish = "app_key=ak&sign=DEADBEEF&user_token=ut"
    monkeypatch.setattr(lazada.httpx, "get",
                        lambda *a, **k: _Resp(status=500, text=secret_ish))
    with pytest.raises(lazada.LazadaError) as exc:
        lazada._call("/x", {})
    message = str(exc.value)
    assert "sign=" not in message and "app_key" not in message and "user_token" not in message
    assert "500" in message


def test_lazada_api_error_without_a_message_does_not_dump_the_payload(monkeypatch):
    _configure_lazada(monkeypatch)
    payload = {"code": "9999", "request_id": "abc", "internal": "app_key=ak"}
    monkeypatch.setattr(lazada.httpx, "get", lambda *a, **k: _Resp(payload=payload))
    with pytest.raises(lazada.LazadaError) as exc:
        lazada._call("/x", {})
    assert "app_key" not in str(exc.value)
    assert "9999" in str(exc.value)


# --------------------------------------------------------------------------
# Resend
# --------------------------------------------------------------------------

def test_resend_rejection_does_not_echo_the_body(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "email_provider", "resend", raising=False)
    monkeypatch.setattr(settings, "resend_api_key", "re_test", raising=False)
    body = '{"message":"Invalid `to` field","to":["victim@example.com"]}'
    monkeypatch.setattr(email_adapter.httpx, "post",
                        lambda *a, **k: _Resp(status=422, text=body))
    with pytest.raises(email_adapter.EmailSendError) as exc:
        email_adapter.send_otp_email("victim@example.com", "123456")
    message = str(exc.value)
    assert "victim@example.com" not in message, "recipient PII reached the error string"
    assert "422" in message


def test_resend_never_puts_the_code_in_the_error(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "email_provider", "resend", raising=False)
    monkeypatch.setattr(settings, "resend_api_key", "re_test", raising=False)
    monkeypatch.setattr(email_adapter.httpx, "post",
                        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    with pytest.raises(email_adapter.EmailSendError) as exc:
        email_adapter.send_otp_email("someone@example.com", "918273")
    assert "918273" not in str(exc.value), "the one-time code reached the error string"


# --------------------------------------------------------------------------
# Cache directives on authenticated responses
# --------------------------------------------------------------------------

def test_authenticated_responses_are_never_shared_cacheable(client):
    """A per-user payload must not be marked `public`.

    The platform default was `public, max-age=0, must-revalidate` on every
    response, /auth/me included. must-revalidate makes exploitation unlikely,
    but `public` on per-user data is the wrong signal and it only takes one CDN
    rule or one lenient intermediary for it to become one user's data served to
    another.
    """
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer whatever"})
    cache = resp.headers.get("cache-control", "")
    assert "private" in cache and "no-store" in cache, cache
    assert "public" not in cache, cache
    assert "Authorization" in resp.headers.get("vary", "")


def test_anonymous_responses_keep_their_cacheability(client):
    """The fix must key on credentials, not on the path.

    The same endpoints serve both audiences - the feed returns `my_vote` only
    when a token is present - so an anonymous read stays cacheable while the
    credentialed version of the same route does not.
    """
    resp = client.get("/health")
    assert "no-store" not in (resp.headers.get("cache-control") or "")
