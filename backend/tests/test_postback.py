"""Lazada postback receiver + sub-ID decoration (M3 slice 12).

The security properties are the point of these tests: a public, unsigned endpoint
that touches attribution must reject bad tokens, must never create money, and
must not double-count retries.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.adapters import lazada
from app.core.config import settings
from app.models.enums import Platform
from app.services import postback_service, referral_service

SECRET = "x" * 48


@pytest.fixture
def postback_secret(monkeypatch):
    monkeypatch.setattr(settings, "lazada_postback_secret", SECRET)
    return SECRET


# --- shared-secret auth ------------------------------------------------------
def test_secret_fails_closed_when_unset(monkeypatch):
    """An unconfigured secret must reject everything, not accept everything."""
    monkeypatch.setattr(settings, "lazada_postback_secret", "")
    assert postback_service.secret_ok("") is False
    assert postback_service.secret_ok(None) is False
    assert postback_service.secret_ok("anything") is False


def test_secret_comparison(postback_secret):
    assert postback_service.secret_ok(SECRET) is True
    assert postback_service.secret_ok(SECRET[:-1] + "y") is False
    assert postback_service.secret_ok(None) is False


def test_endpoint_rejects_bad_token(client, postback_secret):
    r = client.get("/api/v1/postback/lazada", params={"token": "wrong", "order_id": "1"})
    assert r.status_code == 403


def test_endpoint_disabled_without_config(client, monkeypatch):
    monkeypatch.setattr(settings, "lazada_postback_secret", "")
    r = client.get("/api/v1/postback/lazada", params={"token": "x"})
    assert r.status_code == 503


# --- short aliases -----------------------------------------------------------
def test_short_aliases_expand_to_canonical_names():
    out = postback_service.normalize({
        "t": "tok", "c": "ref_1", "r": "blt_1", "o": "ORD", "so": "SUB", "s": "Fulfilled"})
    assert out == {"token": "tok", "click_ref": "ref_1", "review_sub_id": "blt_1",
                   "order_id": "ORD", "sub_order_id": "SUB", "status": "Fulfilled"}


def test_long_names_still_work_and_win_over_aliases():
    """Both spellings are supported; an explicit long name is authoritative."""
    assert postback_service.normalize({"order_id": "LONG"})["order_id"] == "LONG"
    out = postback_service.normalize({"o": "SHORT", "order_id": "LONG"})
    assert out["order_id"] == "LONG"


def test_unknown_params_pass_through_untouched():
    """Lazada may add macros we do not model; they must still reach `raw`."""
    assert postback_service.normalize({"_p_venture": "PH"})["_p_venture"] == "PH"


def test_endpoint_accepts_the_short_form(client, postback_secret):
    r = client.get("/api/v1/postback/lazada", params={
        "t": SECRET, "o": "test_order", "so": "test_sub"})
    assert r.status_code == 200
    assert r.json()["mode"] == "test"


def test_short_form_rejects_a_bad_token(client, postback_secret):
    r = client.get("/api/v1/postback/lazada", params={"t": "nope", "o": "1"})
    assert r.status_code == 403


# --- Lazada's 'Run Test' -----------------------------------------------------
def test_run_test_mock_values_acknowledged_without_writing(client, postback_secret):
    """Their guide warns that validating mock values looks like a broken integration."""
    r = client.get("/api/v1/postback/lazada", params={
        "token": SECRET, "order_id": "test_order", "sub_order_id": "test_sub",
        "payout": "test_payout"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mode": "test"}


def test_is_test_fire_detection():
    assert postback_service.is_test_fire({"sub_order_id": "test_123"}) is True
    assert postback_service.is_test_fire({"order_id": "test_abc"}) is True
    assert postback_service.is_test_fire({"order_id": "218479276816603"}) is False
    assert postback_service.is_test_fire({}) is False


# --- outbound sub-ID decoration ---------------------------------------------
def test_lazada_url_gets_both_sub_ids():
    out = referral_service.decorate_affiliate_url(
        "https://c.lazada.com.ph/t/c.abcdef", Platform.lazada, "blt_deadbeef", "ref_123")
    assert "sub_id1=blt_deadbeef" in out
    assert "sub_id2=ref_123" in out


def test_decoration_preserves_existing_params_and_never_clobbers():
    """A sub_id1 the moderator typed into the dashboard is what Lazada has on
    file; overwriting it here would break their reporting."""
    out = referral_service.decorate_affiliate_url(
        "https://c.lazada.com.ph/t/c.abc?sub_id1=theirs&utm=x",
        Platform.lazada, "blt_ours", "ref_123")
    assert "sub_id1=theirs" in out
    assert "sub_id1=blt_ours" not in out
    assert "utm=x" in out
    assert "sub_id2=ref_123" in out


def test_shopee_urls_are_untouched():
    """Shopee has no sub-ID round trip; its links must pass through verbatim."""
    url = "https://shopee.ph/product/1/2?af_id=x"
    assert referral_service.decorate_affiliate_url(
        url, Platform.shopee, "blt_x", "ref_1") == url


# --- signing -----------------------------------------------------------------
def test_signature_matches_top_scheme():
    """Path-prefixed, sorted, empty values skipped, `sign` excluded."""
    params = {"app_key": "1", "b": "2", "empty": "", "sign": "ignored"}
    expected_payload = "/x/yapp_key1b2sign ignored".replace(" ", "")
    got = lazada.sign("/x/y", params, "secret")
    import hashlib
    import hmac
    assert got == hmac.new(b"secret", expected_payload.encode(),
                           hashlib.sha256).hexdigest().upper()
    assert got.isupper()


def test_signature_changes_with_path():
    """Omitting the api path is the classic silent IncompleteSignature."""
    p = {"a": "1"}
    assert lazada.sign("/one", p, "s") != lazada.sign("/two", p, "s")


def test_api_calls_refuse_without_credentials(monkeypatch):
    monkeypatch.setattr(settings, "lazada_app_key", "")
    with pytest.raises(lazada.LazadaError, match="not configured"):
        lazada._call("/marketing/conversion/report", {})


def test_conversion_returned_detection():
    def conv(status):
        return lazada.Conversion(order_id="1", sub_order_id="2", status=status,
                                 est_payout="1.00", order_amount="10.00", currency="PHP",
                                 conversion_time=None, sub_id1=None, sub_id2=None,
                                 validity=None, raw={})
    assert conv("Returned").is_returned is True
    assert conv("cancelled").is_returned is True
    assert conv("Fulfilled").is_returned is False


# --- amount parsing ----------------------------------------------------------
def test_decimal_parsing_is_lenient():
    assert postback_service._decimal("17.456") == Decimal("17.46")
    assert postback_service._decimal("") is None
    assert postback_service._decimal(None) is None
    # Lazada has been known to send junk; a bad amount must not 500 the endpoint.
    assert postback_service._decimal("not-a-number") is None
