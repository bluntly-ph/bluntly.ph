"""Marketplace conversion postbacks (M3 slice 12) — Lazada.

**A postback is evidence, never money.**

Lazada's macro set contains no request signature; the endpoint is authenticated
only by a shared secret embedded in the URL we register with them. A URL is not a
credential you can rotate quietly, it appears in their dashboard, and it travels
in query strings that get logged. Treating that as authority to mint commissions
would mean anyone who ever sees the URL can pay themselves.

So this module does exactly two things:
  1. records what Lazada claimed, in `affiliate_postbacks`, verbatim; and
  2. flips the originating click to `converted` so the funnel is honest.

Commissions come from a signed source — `lazada_client.fetch_conversions` against
`/marketing/conversion/report`, or the admin CSV for Shopee — which then links
back here through `reconciled_commission_id`.

Attribution keys, echoed back by Lazada from the tracking link:
  * `subId2` -> `sessions.click_ref`  — the exact click (set by the redirect)
  * `subId1` -> `referral_links.sub_id` — the review (set by the moderator)
Click-level wins; review-level is the fallback when a link predates per-click
tagging or a moderator hand-built the URL.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import ConversionStatus, Platform
from app.models.postback import AffiliatePostback
from app.models.review import ReferralLink
from app.models.session import Session as ClickSession

log = get_logger("postback")

# Lazada's 'Run Test' button fires mock values (documented: all values arrive as
# test_XXX). Their troubleshooting guide is explicit that a server rejecting them
# looks like a failed integration, so we acknowledge without writing anything.
_TEST_PREFIX = "test_"

# Statuses Lazada may report. Only `returned` is terminal-negative; the rest are
# stages on the way to payable. We store the raw string either way.
NEGATIVE_STATUSES = {"returned", "cancelled", "canceled", "invalid"}


# Short aliases for the postback URL. Lazada's `{...}` macros are fixed — they are
# how Lazada names its own data, and it substitutes only the ones literally
# present in the URL you register. The *parameter names*, though, are ours, so a
# one-letter form roughly halves the string a human has to paste into their
# dashboard without losing anything. Both spellings are accepted forever; the long
# form is what appears in logs and tests.
_ALIASES = {
    "t": "token",
    "c": "click_ref",
    "r": "review_sub_id",
    "o": "order_id",
    "so": "sub_order_id",
    "s": "status",
    "p": "payout",
    "a": "amount",
    "cur": "currency",
    "ot": "order_type",
    "at": "attribution",
    "ct": "conversion_time",
}


def normalize(params: dict[str, str]) -> dict[str, str]:
    """Expand short aliases to canonical names. Explicit long names win."""
    out: dict[str, str] = {}
    for key, value in params.items():
        out.setdefault(_ALIASES.get(key, key), value)
    for key, value in params.items():
        canonical = _ALIASES.get(key, key)
        if canonical == key:
            out[key] = value  # an explicit long name overrides its alias
    return out


def secret_ok(supplied: str | None) -> bool:
    """Constant-time comparison against the configured postback secret.

    Returns False when no secret is configured: an unset secret must fail closed,
    otherwise enabling the feature by accident would expose an open money-adjacent
    endpoint.
    """
    expected = settings.lazada_postback_secret
    if not expected or not supplied:
        return False
    return secrets.compare_digest(supplied, expected)


def is_test_fire(params: dict[str, str]) -> bool:
    """True when this looks like Lazada's 'Run Test', which sends mock values."""
    interesting = (params.get("sub_order_id"), params.get("order_id"),
                   params.get("click_ref"), params.get("review_sub_id"))
    return any(v and str(v).startswith(_TEST_PREFIX) for v in interesting)


def _decimal(raw: str | None) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _resolve_attribution(db: Session, click_ref: str | None,
                         review_sub_id: str | None
                         ) -> tuple[ClickSession | None, uuid.UUID | None]:
    """(session, review_id) from the echoed sub-IDs. Click-level preferred."""
    if click_ref:
        session = db.scalar(select(ClickSession).where(
            ClickSession.click_ref == click_ref))
        if session is not None:
            return session, session.review_id
    if review_sub_id:
        link = db.scalar(select(ReferralLink).where(
            ReferralLink.sub_id == review_sub_id))
        if link is not None:
            return None, link.review_id
    return None, None


def record_lazada_postback(db: Session, params: dict[str, str]) -> dict:
    """Persist one Lazada order postback. Idempotent per sub-order.

    Never raises on unrecognised input: an error response makes Lazada mark the
    integration unhealthy, and a postback we cannot attribute is still evidence
    worth keeping. Unattributed rows land with session_id/review_id NULL and are
    visible to admins.
    """
    now = datetime.now(UTC)
    sub_order_id = params.get("sub_order_id") or None
    order_id = params.get("order_id") or None
    click_ref = params.get("click_ref") or None
    review_sub_id = params.get("review_sub_id") or None

    # Idempotency: Lazada retries, and D+1 delivery can overlap a manual replay.
    if sub_order_id:
        existing = db.scalar(select(AffiliatePostback).where(
            AffiliatePostback.platform == Platform.lazada,
            AffiliatePostback.external_sub_order_id == sub_order_id))
        if existing is not None:
            # A later fire carries a newer status (fulfilled -> delivered/returned).
            status = params.get("status") or None
            if status and status != existing.order_status:
                existing.order_status = status
                existing.raw = {**(existing.raw or {}), "latest": dict(params)}
                db.commit()
                log.info("postback status advanced", extra={"extra_fields": {
                    "sub_order_id": sub_order_id, "status": status}})
                return {"status": "updated", "id": str(existing.id)}
            return {"status": "duplicate", "id": str(existing.id)}

    session, review_id = _resolve_attribution(db, click_ref, review_sub_id)

    row = AffiliatePostback(
        platform=Platform.lazada,
        event_type="order",
        external_order_id=order_id,
        external_sub_order_id=sub_order_id,
        click_ref=click_ref,
        review_sub_id=review_sub_id,
        session_id=session.id if session else None,
        review_id=review_id,
        reported_payout=_decimal(params.get("payout")),
        reported_amount=_decimal(params.get("amount")),
        currency=(params.get("currency") or None),
        order_status=(params.get("status") or None),
        order_type=(params.get("order_type") or None),
        attribution_type=(params.get("attribution") or None),
        conversion_time=(params.get("conversion_time") or None),
        raw=dict(params),
        received_at=now,
    )
    db.add(row)

    # The funnel signal: this click produced an order. Deliberately does NOT
    # touch any wallet — `sessions.order_ref` is what the signed reconciliation
    # later matches on.
    if session is not None:
        status = (params.get("status") or "").strip().lower()
        session.conversion_status = (ConversionStatus.cancelled
                                     if status in NEGATIVE_STATUSES
                                     else ConversionStatus.converted)
        session.order_ref = order_id or session.order_ref
        session.order_status = params.get("status") or session.order_status

    db.commit()
    log.info("postback recorded", extra={"extra_fields": {
        "sub_order_id": sub_order_id, "attributed": session is not None,
        "review_id": str(review_id) if review_id else None}})
    return {"status": "recorded", "id": str(row.id),
            "attributed": session is not None}
