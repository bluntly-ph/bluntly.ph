"""Simulated GCash / Maya payouts (completion contract X.4), without a database.

PRD FR-6 pays out through PayPal only; GCash and Maya wait on a business
permit, BIR and DTI registration (RA 11967). The completion contract asks for
them *simulated*. On a money screen the one thing a simulation must never do is
move money, or look as if it did, so these rules are pinned:

* **No side effects.** The simulation module reads a balance and returns a
  description. It does not create payout rows, adjust a wallet, or talk to a
  provider — checked on its source, so a later "convenience" cannot slip in.
* **It says it is a simulation**, every time, and names the rail that actually
  pays (PayPal).
* **The ₱300 minimum applies** exactly as it does to a real payout: below it,
  the preview says how far off the reviewer is and shows no timeline.
"""

from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal

import pytest

from app.services import payout_simulation
from app.services.payout_simulation import simulate
from tests.test_seller_api_contract import _needs_account, _routes

MIN = Decimal("300")
TODAY = date(2026, 9, 14)


def test_at_the_minimum_the_whole_balance_would_be_paid():
    result = simulate(Decimal("300.00"), "gcash", minimum=MIN, today=TODAY)
    assert result.eligible is True
    assert result.amount == Decimal("300.00")
    assert result.short_by == Decimal("0.00")
    assert [step.status for step in result.steps] == ["scheduled", "processing", "paid"]


def test_below_the_minimum_there_is_no_timeline_only_the_gap():
    result = simulate(Decimal("212.50"), "maya", minimum=MIN, today=TODAY)
    assert result.eligible is False
    assert result.amount == Decimal("0.00")
    assert result.short_by == Decimal("87.50")
    assert result.steps == []


@pytest.mark.parametrize("rail, name", [("gcash", "GCash"), ("maya", "Maya")])
def test_the_timeline_names_the_rail(rail, name):
    result = simulate(Decimal("450"), rail, minimum=MIN, today=TODAY)
    assert any(name in step.label for step in result.steps)


@pytest.mark.parametrize("wallet", [Decimal("0"), Decimal("300"), Decimal("1200.75")])
def test_it_always_says_it_is_a_simulation_and_what_really_pays(wallet):
    result = simulate(wallet, "gcash", minimum=MIN, today=TODAY)
    assert result.simulated is True
    assert result.real_rail == "paypal"
    assert "no money moves" in result.disclaimer.lower()


def test_an_unknown_rail_is_refused():
    with pytest.raises(ValueError):
        simulate(Decimal("500"), "bank_transfer", minimum=MIN, today=TODAY)


def test_the_simulation_cannot_touch_money():
    source = inspect.getsource(payout_simulation)
    # The money paths, by name: payout rows, the wallet service, the provider
    # adapters, and any session write. (Naming PayPal as the rail that really
    # pays is fine; calling it is not.)
    for forbidden in ("Payout(", "app.models.payout", "app.services.wallet", "wallet.adjust",
                      "app.adapters", "db.add", ".commit(", "Session"):
        assert forbidden not in source, f"the simulation module must not use {forbidden!r}"


def test_the_preview_is_a_read_and_needs_an_account():
    route = _routes()[("GET", "/api/v1/payouts/simulate")]
    assert _needs_account(route)
