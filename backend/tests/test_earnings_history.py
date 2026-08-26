"""The reviewer's own earnings history (History screen, frame 5762:472).

The screen shows a reviewer where their money went, so the assertions here are
about not misrepresenting it: not showing someone else's, not counting a
reversal twice, and not calling an unpaid sale paid.
"""

from __future__ import annotations

import pytest

from app.services import dashboard_service as svc
from tests.conftest import register_and_token, requires_db

ENDPOINT = "/api/v1/users/me/earnings"


# Authorization -------------------------------------------------------------

@requires_db
def test_anonymous_is_denied(client):
    assert client.get(ENDPOINT).status_code in (401, 403)


@requires_db
def test_a_signed_in_reviewer_sees_their_own(client):
    _, token, _ = register_and_token(client, role="user")
    resp = client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows"] == [] and body["all_time"] == "0"


@requires_db
def test_there_is_no_way_to_ask_for_someone_elses(client):
    """The route takes no user id. An endpoint that accepts one is an endpoint
    somebody eventually passes a different one to."""
    _, token, _ = register_and_token(client, role="user")
    other = "00000000-0000-0000-0000-0000000000aa"
    headers = {"Authorization": f"Bearer {token}"}
    # Neither a path variant nor a query parameter may select another user.
    assert client.get(f"/api/v1/users/{other}/earnings",
                      headers=headers).status_code == 404
    body = client.get(f"{ENDPOINT}?user_id={other}", headers=headers).json()
    assert body["rows"] == [], "a query parameter selected another user's earnings"


# Privacy -------------------------------------------------------------------

@requires_db
def test_the_response_carries_no_identity_or_address(client):
    _, token, _ = register_and_token(client, role="user")
    raw = client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"}).text.lower()
    for forbidden in ("email", "wallet_balance", "password", "ip_address",
                      "receipt_key", "session"):
        assert forbidden not in raw, f"{forbidden} leaked into the earnings response"


# Filters -------------------------------------------------------------------

@requires_db
@pytest.mark.parametrize("status", ["all", "pending", "to_earn", "paid", "returned"])
def test_every_designed_tab_is_accepted(client, status):
    """The frame's tabs are All / Pending / To earn / Returned; `paid` is the
    fourth canonical settlement state and is offered alongside them."""
    _, token, _ = register_and_token(client, role="user")
    resp = client.get(f"{ENDPOINT}?status={status}",
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@requires_db
def test_an_unknown_filter_is_refused_not_silently_widened(client):
    """Silently answering "all" to an unrecognised filter shows a reviewer more
    than they asked for and calls it the thing they asked for."""
    _, token, _ = register_and_token(client, role="user")
    resp = client.get(f"{ENDPOINT}?status=everything",
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


def test_the_service_refuses_an_unknown_filter():
    with pytest.raises(ValueError):
        svc.earnings_history(None, None, status="everything")


def test_the_tabs_cover_the_canonical_settlement_states():
    """`to_earn` and `paid` must stay distinct. Collapsing them would tell a
    reviewer money had arrived when it has only been recognised."""
    assert {"pending", "to_earn", "paid", "returned"} <= set(svc.EARNING_FILTERS)


# Status derivation ---------------------------------------------------------

class _FakePostback:
    def __init__(self, lifecycle, settlement):
        self.canonical_status = lifecycle
        self.settlement_status = settlement


class _FakeCommission:
    def __init__(self, reverses=None):
        self.reverses_commission_id = reverses


@pytest.mark.parametrize("lifecycle,settlement,expected", [
    ("pending", "not_earned", "pending"),
    ("completed", "earned", "to_earn"),
    ("completed", "paid", "paid"),
    ("returned", "reversed", "returned"),
    # The case the whole absorb policy exists for: returned AFTER payout. It
    # must read as returned, not as paid.
    ("returned", "paid", "returned"),
    # Completed but unattributable — recognised nothing, so it is not "paid".
    ("completed", "not_earned", "to_earn"),
])
def test_status_is_derived_from_the_canonical_pair(lifecycle, settlement, expected):
    got = svc._earning_status(_FakeCommission(), _FakePostback(lifecycle, settlement))
    assert got == expected


def test_a_reversal_entry_is_never_shown_as_its_own_earning():
    """A reviewer wants to see the sale and that it came back, not two rows that
    look like two events."""
    assert svc._earning_status(_FakeCommission(reverses="x"), None) == "returned"


def test_a_commission_with_no_postback_is_owed_not_paid():
    """Legacy CSV imports carry no canonical transaction. The safe reading is
    that the money is owed, never that it has already been sent."""
    assert svc._earning_status(_FakeCommission(), None) == "to_earn"
