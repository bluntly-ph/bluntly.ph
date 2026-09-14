"""Simulated GCash / Maya payouts (completion contract X.4).

PRD FR-6 pays out through PayPal only: GCash and Maya are future work pending a
business permit, BIR and DTI registration under RA 11967. The completion
contract asks for them *simulated*, so this module describes what a payout of
the reviewer's current balance would look like on either rail — and does
nothing else.

It is deliberately a pure function over a balance. It never creates a payout
row, never adjusts a wallet, never reaches a provider, and never touches a
database session; `tests/test_payout_simulation_rules.py` checks its source for
each of those, so a later convenience cannot quietly turn a preview into a
transfer. The same ₱300 minimum as a real payout applies.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel

SimulatedRail = Literal["gcash", "maya"]

_RAIL_NAMES: dict[str, str] = {"gcash": "GCash", "maya": "Maya"}
_CENT = Decimal("0.01")


class SimulationStep(BaseModel):
    status: Literal["scheduled", "processing", "paid"]
    label: str


class SimulationOut(BaseModel):
    #: Always true. The field exists so no client can mistake this for a payout.
    simulated: bool = True
    rail: SimulatedRail
    #: The rail that actually pays today.
    real_rail: str = "paypal"
    eligible: bool
    #: What would be paid: the whole balance when eligible, otherwise nothing.
    amount: Decimal
    minimum: Decimal
    #: How far below the minimum the balance is; zero when eligible.
    short_by: Decimal
    currency: str = "PHP"
    steps: list[SimulationStep]
    disclaimer: str
    as_of: date


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def simulate(wallet: Decimal, rail: str, *, minimum: Decimal, today: date) -> SimulationOut:
    """Describe a payout of `wallet` on `rail`. Returns a description only."""
    if rail not in _RAIL_NAMES:
        raise ValueError(f"Unknown simulated rail: {rail!r}")
    name = _RAIL_NAMES[rail]
    balance = _money(wallet)
    floor = _money(minimum)
    eligible = balance >= floor

    steps = [
        SimulationStep(status="scheduled",
                       label=("Your balance would be reserved from your wallet "
                              "for the next payout batch")),
        SimulationStep(status="processing", label=f"It would be sent to your {name} account"),
        SimulationStep(status="paid", label=f"It would arrive in your {name} wallet"),
    ] if eligible else []

    return SimulationOut(
        rail=rail,  # type: ignore[arg-type]
        eligible=eligible,
        amount=balance if eligible else _money(Decimal("0")),
        minimum=floor,
        short_by=_money(Decimal("0")) if eligible else floor - balance,
        steps=steps,
        disclaimer=(f"Simulation only. No money moves and your balance is unchanged. "
                    f"Payouts are paid through PayPal today; {name} needs a business permit, "
                    f"BIR and DTI registration first."),
        as_of=today,
    )
