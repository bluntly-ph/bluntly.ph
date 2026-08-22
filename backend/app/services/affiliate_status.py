"""Provider status vocabulary -> the four canonical lifecycle states.

This is the adapter boundary. Everything downstream — dashboards, earnings,
payouts, the wallet — speaks `AffiliateTxStatus` and never asks which
marketplace a row came from. `if shopee: ... elif lazada:` belongs here and
nowhere else.

Every rule below is derived from the real reports and the live API, not from
provider documentation alone, and the evidence is recorded beside each one
because both providers have a case where the obvious mapping is wrong.

Pure functions: no database, no network, no I/O. That is what makes the money
rules testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.models.enums import AffiliateTxStatus


@dataclass(frozen=True)
class Mapped:
    """A canonical status plus why it was chosen, for the audit trail."""

    status: AffiliateTxStatus
    reason: str
    #: The provider's own words, preserved verbatim so a moderator can see what
    #: the marketplace actually said rather than only our translation of it.
    raw_order_status: str | None = None
    raw_item_status: str | None = None


def _money(value: object) -> Decimal:
    """A provider money field as a Decimal, or zero. Never raises."""
    if value is None:
        return Decimal("0")
    text = str(value).replace(",", "").replace("₱", "").strip()
    if not text or text in {"-", "--"}:
        return Decimal("0")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


#: Values a provider uses to mean "this field does not apply to this row".
#: Lazada fills `Returned Time` on **every** row of its export and writes the
#: literal `N/A` where nothing was returned — so a truthiness check on that
#: column marks all 218 rows as returned. Caught only by running the mapper
#: over the real file.
_ABSENT = {"", "-", "--", "n/a", "na", "null", "none", "0000-00-00"}


def _present(value: object) -> str | None:
    """A provider field's value, or None when the provider means 'not set'."""
    text = str(value or "").strip()
    return text if text.lower() not in _ABSENT else None


# --------------------------------------------------------------------------
# Shopee
# --------------------------------------------------------------------------

#: Shopee reports a status for the *order* and a status for the *affiliate
#: item*, and they can disagree. In the owner's 108-row report the pairs are:
#:
#:     (Pending, Pending)     8
#:     (Completed, Completed) 95
#:     (Cancelled, Cancelled) 3
#:     (Completed, Cancelled) 2   <- the case that matters
#:
#: Both of those two rows carry `Item Note = "Order is invalid."` and a positive
#: `Refund Amount` (474.00 and 249.00). One of them *still reports a commission
#: of 15.12*. So the commission figure on a cancelled item is not trustworthy,
#: and the order-level status is not the affiliate's status: the buyer completed
#: the order, then the item was refunded and the affiliate credit withdrawn.
#:
#: Hence: the item status wins, and refund evidence can only ever downgrade.
SHOPEE_ITEM_STATUS = {
    "completed": AffiliateTxStatus.completed,
    "pending": AffiliateTxStatus.pending,
    "cancelled": AffiliateTxStatus.cancelled,
    "canceled": AffiliateTxStatus.cancelled,
    "returned": AffiliateTxStatus.returned,
    "refunded": AffiliateTxStatus.returned,
}

SHOPEE_ORDER_STATUS = {
    "completed": AffiliateTxStatus.completed,
    "pending": AffiliateTxStatus.pending,
    "cancelled": AffiliateTxStatus.cancelled,
    "canceled": AffiliateTxStatus.cancelled,
}


def map_shopee(row: dict) -> Mapped:
    """Canonical status for one Shopee affiliate item row.

    Precedence, highest first:

    1. `Affiliate Item Status` — the affiliate's own view of this item.
    2. `Order Status` — used only when the item status is missing.
    3. Refund evidence — can downgrade a *completed* result, never upgrade one.

    An unknown status is `pending`, never `completed`: the failure mode of
    guessing "pending" is a commission that arrives late, and the failure mode
    of guessing "completed" is money paid out for a sale that never finalised.
    """
    raw_order = str(row.get("order status") or row.get("Order Status") or "").strip()
    raw_item = str(
        row.get("affiliate item status") or row.get("Affiliate Item Status") or ""
    ).strip()

    item_key, order_key = _norm(raw_item), _norm(raw_order)
    refund = _money(
        row.get("refund amount(₱)")
        or row.get("refund amount")
        or row.get("Refund Amount(₱)")
    )

    if item_key:
        status = SHOPEE_ITEM_STATUS.get(item_key)
        reason = f"affiliate_item_status={raw_item}"
        if status is None:
            status, reason = AffiliateTxStatus.pending, f"unknown_item_status={raw_item}"
    elif order_key:
        status = SHOPEE_ORDER_STATUS.get(order_key)
        reason = f"order_status={raw_order} (no item status)"
        if status is None:
            status, reason = AffiliateTxStatus.pending, f"unknown_order_status={raw_order}"
    else:
        status, reason = AffiliateTxStatus.pending, "no status reported"

    # Refund evidence only ever downgrades. A refunded-but-"completed" row is
    # the exact shape of the two anomalies above, and paying it would be paying
    # for a sale the buyer got their money back on.
    if refund > 0 and status is AffiliateTxStatus.completed:
        return Mapped(AffiliateTxStatus.returned,
                      f"refund_amount={refund} overrides {reason}",
                      raw_order or None, raw_item or None)

    return Mapped(status, reason, raw_order or None, raw_item or None)


# --------------------------------------------------------------------------
# Lazada
# --------------------------------------------------------------------------

#: Lazada's vocabulary is wider than any single source shows.
#:
#: The owner's XLSX export contains only Delivered(162) / Rejected(45) /
#: Returned(11). The **live API** — queried read-only over three months,
#: 101 rows — also returns `Fulfilled`, a state the export never contains:
#:
#:     Fulfilled  5   (valid)
#:     Delivered 64   (valid)
#:     Rejected  25   (24 invalid, 1 VALID)
#:     Returned   7   (valid)
#:
#: Two consequences:
#:
#: `Fulfilled` is an intermediate state — the order has shipped, not landed —
#: so it is PENDING. Treating it as completed would recognise commission on
#: orders that can still be rejected or returned.
#:
#: `Validity` does not track lifecycle. There is a `(Rejected, valid)` row, and
#: every single `Returned` row is `valid`. So validity must not be used to
#: decide payability, and in particular must not rescue a return.
LAZADA_STATUS = {
    "delivered": AffiliateTxStatus.completed,
    "fulfilled": AffiliateTxStatus.pending,
    "pending": AffiliateTxStatus.pending,
    "rejected": AffiliateTxStatus.cancelled,
    "cancelled": AffiliateTxStatus.cancelled,
    "canceled": AffiliateTxStatus.cancelled,
    "returned": AffiliateTxStatus.returned,
    "refunded": AffiliateTxStatus.returned,
}


def map_lazada(row: dict) -> Mapped:
    """Canonical status for one Lazada conversion row (report or API).

    Precedence, highest first:

    1. `Status` — the lifecycle, and the only field that describes it.
    2. `Returned Time` — corroborating evidence; can downgrade to `returned`.
    3. `Validity` — used **only** to reject an otherwise-unknown row, never to
       promote one, because `(Rejected, valid)` and `(Returned, valid)` both
       occur in live data.

    `Payout` is deliberately not consulted. Ten of the eleven returned rows in
    the owner's report carry a positive payout, and the API's own field is named
    `estPayout` — an estimate that moves as the order progresses. Money is not
    evidence of finality.
    """
    raw_status = str(row.get("status") or row.get("Status") or "").strip()
    validity = _norm(row.get("validity") or row.get("Validity"))
    returned_at = _present(row.get("returned time") or row.get("Returned Time"))

    key = _norm(raw_status)
    status = LAZADA_STATUS.get(key)
    reason = f"status={raw_status}"

    if status is None:
        # Unknown word. Validity is the only other signal, and it may only make
        # things worse, never better.
        if validity == "invalid":
            status = AffiliateTxStatus.cancelled
            reason = f"unknown status={raw_status}, validity=invalid"
        else:
            status, reason = AffiliateTxStatus.pending, f"unknown status={raw_status}"

    # A real return timestamp outranks a *stale* status word — but only one that
    # still looks payable or unresolved. It must not reclassify an already
    # terminal-negative row: 5 of the 45 `Rejected` rows in the owner's report
    # carry a genuine return date (the goods came back, then the affiliate
    # credit was refused). Both outcomes are "no money", and `Status` is the
    # provider's own authoritative word for which one it was, so it stands.
    if returned_at and status in {AffiliateTxStatus.completed, AffiliateTxStatus.pending}:
        return Mapped(AffiliateTxStatus.returned,
                      f"returned_time={returned_at} overrides {reason}",
                      raw_status or None, None)

    return Mapped(status, reason, raw_status or None, None)


#: The one place a provider name is turned into a mapper.
MAPPERS = {"shopee": map_shopee, "lazada": map_lazada}


def map_status(platform: str, row: dict) -> Mapped:
    """Canonical status for a row from `platform`.

    An unrecognised platform is `pending` rather than an exception: an import
    that cannot classify a row must still record it for a human to look at,
    and must never classify it as money.
    """
    mapper = MAPPERS.get(_norm(platform))
    if mapper is None:
        return Mapped(AffiliateTxStatus.pending, f"unknown_platform={platform}")
    return mapper(row)
