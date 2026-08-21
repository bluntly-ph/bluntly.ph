"""Earnings payouts + scheduling by membership tier (M3 slice 11).

Scheduling order IS the "payment scheduling by membership tier" requirement:
users are selected in `membership_tiers.payout_priority` order (special ->
founding -> standard).

Money safety rule: the wallet is debited **when the payout is scheduled**, not
when it is paid. The balance is therefore reserved while a batch is in flight and
cannot be spent twice; `failed` and `cancelled` refund it. Every state change
goes through one of the helpers here so that invariant holds:

    wallet == inflows - SUM(payouts in scheduled/processing/paid)
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters import paypal
from app.core.config import settings
from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.models.enums import (
    ModerationAction,
    PayoutMethod,
    PayoutStatus,
)
from app.models.membership import MembershipTierConfig
from app.models.moderation import ModerationLog
from app.models.payout import Payout
from app.models.user import User
from app.services import wallet

log = get_logger("payouts")

# Money has left the wallet in these states; failed/cancelled put it back.
RESERVED_STATES = (PayoutStatus.scheduled, PayoutStatus.processing, PayoutStatus.paid)


def _now() -> datetime:
    return datetime.now(UTC)


def _conflict(detail: str, code: str) -> AppError:
    return AppError(detail, code=code, status_code=409, title="Conflicting state")


def current_method() -> PayoutMethod:
    try:
        return PayoutMethod(settings.payout_provider)
    except ValueError:
        return PayoutMethod.manual


def batch_id_for(when: date) -> str:
    return f"batch_{when:%Y%m}"



def _locked(db: Session, payout: Payout) -> Payout:
    """Re-read a payout FOR UPDATE so its state check cannot race.

    Every transition here guards on the current status - "only a scheduled
    payout can be cancelled". Read outside a lock, two concurrent callers both
    see `scheduled`, both pass the guard, and both refund. The guard reads like
    a state machine while behaving like a suggestion.

    `populate_existing` matters: without it the identity map hands back the
    same stale instance that was checked a moment ago, and the lock buys
    nothing.
    """
    return db.execute(
        select(Payout)
        .where(Payout.id == payout.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def schedule_payouts(db: Session, when: date | None = None,
                     triggered_by: uuid.UUID | None = None) -> dict:
    """Create payouts for every eligible user, tier-priority first.

    Eligible = wallet_balance >= PAYOUT_MIN_PHP AND payout_account set. Users
    without a payout account are skipped and counted (they are not an error —
    they just haven't told us where to send it).
    """
    when = when or _now().date()
    batch = batch_id_for(when)
    method = current_method()

    priority = {c.code: c.payout_priority
                for c in db.scalars(select(MembershipTierConfig))}
    candidates = db.scalars(
        select(User).where(User.wallet_balance >= settings.payout_min_php)).all()
    # Tier priority (lower first), then largest balance — deterministic ordering.
    candidates.sort(key=lambda u: (priority.get(u.membership_tier, 999),
                                   -u.wallet_balance))

    created: list[Payout] = []
    skipped_no_account = 0
    skipped_existing = 0
    for user in candidates:
        if not user.payout_account:
            skipped_no_account += 1
            continue
        amount = Decimal(user.wallet_balance).quantize(Decimal("0.01"))
        payout = Payout(
            payout_id=f"pay_{uuid.uuid4().hex[:12]}", user_id=user.id,
            amount=amount, currency="PHP", status=PayoutStatus.scheduled,
            method=method, batch_id=batch, scheduled_for=when,
        )
        try:
            # add() MUST be inside the savepoint: on a uq_payout_user_batch
            # violation the rollback then expunges the pending row instead of
            # retrying it on the next flush (same trap as token_service.grant).
            with db.begin_nested():
                db.add(payout)
                db.flush()
        except IntegrityError:
            skipped_existing += 1
            continue
        # Reserve the money immediately.
        wallet.adjust(db, user.id, -amount)
        created.append(payout)

    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        moderator_id=triggered_by, action=ModerationAction.payout,
        notes="payout batch scheduled",
        context={"batch_id": batch, "scheduled": len(created),
                 "total": str(sum((p.amount for p in created), Decimal("0"))),
                 "skipped_no_payout_account": skipped_no_account,
                 "skipped_already_in_batch": skipped_existing,
                 "method": method.value},
    ))
    db.commit()
    result = {"batch_id": batch, "scheduled": len(created),
              "skipped_no_payout_account": skipped_no_account,
              "skipped_already_in_batch": skipped_existing,
              "method": method.value}
    log.info("payout batch scheduled", extra={"extra_fields": result})
    return result


def submit_batch(db: Session, batch: str) -> dict:
    """Hand a scheduled batch to the provider. Missing credentials is NOT an
    error: the batch stays `scheduled` and can be paid manually."""
    payouts = db.scalars(select(Payout).where(
        Payout.batch_id == batch, Payout.status == PayoutStatus.scheduled)).all()
    if not payouts:
        return {"batch_id": batch, "submitted": 0, "status": "nothing_to_submit"}
    if current_method() == PayoutMethod.manual:
        return {"batch_id": batch, "submitted": 0, "status": "manual_mode"}
    if not paypal.is_configured():
        log.info("paypal not configured; batch left scheduled for manual payment",
                 extra={"extra_fields": {"batch_id": batch, "payouts": len(payouts)}})
        return {"batch_id": batch, "submitted": 0, "status": "provider_not_configured"}

    items = [paypal.PayoutItem(receiver=db.get(User, p.user_id).payout_account,
                               amount=p.amount, sender_item_id=p.payout_id)
             for p in payouts]
    try:
        result = paypal.submit_batch(batch, items)
    except (paypal.PayPalError, paypal.PayPalNotConfigured) as exc:
        log.info("paypal submit failed; batch stays scheduled",
                 extra={"extra_fields": {"batch_id": batch, "error": str(exc)}})
        return {"batch_id": batch, "submitted": 0, "status": "submit_failed",
                "error": str(exc)}
    for p in payouts:
        p.status = PayoutStatus.processing
        p.provider_ref = result.payout_batch_id
    db.commit()
    return {"batch_id": batch, "submitted": len(payouts), "status": "processing",
            "provider_ref": result.payout_batch_id}


def refresh_batch(db: Session, batch: str) -> dict:
    """Poll the provider and settle each payout: SUCCESS -> paid; a terminal
    failure -> failed + wallet refunded."""
    payouts = db.scalars(select(Payout).where(
        Payout.batch_id == batch, Payout.status == PayoutStatus.processing)).all()
    if not payouts:
        return {"batch_id": batch, "updated": 0, "status": "nothing_processing"}
    ref = next((p.provider_ref for p in payouts if p.provider_ref), None)
    if not ref:
        return {"batch_id": batch, "updated": 0, "status": "no_provider_ref"}
    try:
        remote = paypal.get_batch(ref)
    except (paypal.PayPalError, paypal.PayPalNotConfigured) as exc:
        return {"batch_id": batch, "updated": 0, "status": "poll_failed",
                "error": str(exc)}

    paid = failed = 0
    batch_status = remote.get("batch_status")
    for p in payouts:
        txn = (remote.get("items") or {}).get(p.payout_id)
        if txn == paypal.TXN_SUCCESS:
            mark_paid(db, p, provider_ref=ref, commit=False)
            paid += 1
        elif txn in paypal.TXN_FAILURES or batch_status in paypal.TERMINAL_FAILURE_BATCH:
            mark_failed(db, p, reason=f"provider status {txn or batch_status}",
                        commit=False)
            failed += 1
        # PENDING / UNCLAIMED / ONHOLD stay `processing` — not settled yet.
    db.commit()
    return {"batch_id": batch, "updated": paid + failed, "paid": paid,
            "failed": failed, "batch_status": batch_status}


def mark_paid(db: Session, payout: Payout, provider_ref: str | None = None,
              commit: bool = True) -> Payout:
    payout = _locked(db, payout)
    if payout.status not in (PayoutStatus.scheduled, PayoutStatus.processing):
        raise _conflict("Only a scheduled or processing payout can be marked paid.",
                        "payout_not_payable")
    payout.status = PayoutStatus.paid
    payout.paid_at = _now()
    if provider_ref:
        payout.provider_ref = provider_ref
    if commit:
        db.commit()
        db.refresh(payout)
    return payout


def mark_failed(db: Session, payout: Payout, reason: str,
                commit: bool = True) -> Payout:
    """Failure refunds the reserved wallet money — the user keeps their earnings."""
    payout = _locked(db, payout)
    if payout.status not in (PayoutStatus.scheduled, PayoutStatus.processing):
        raise _conflict("Only a scheduled or processing payout can fail.",
                        "payout_not_failable")
    payout.status = PayoutStatus.failed
    payout.failure_reason = reason
    wallet.adjust(db, payout.user_id, payout.amount)
    if commit:
        db.commit()
        db.refresh(payout)
    return payout


def cancel(db: Session, payout: Payout) -> Payout:
    """Admin cancel — only while still scheduled (nothing has been submitted)."""
    payout = _locked(db, payout)
    if payout.status != PayoutStatus.scheduled:
        raise _conflict("Only a scheduled payout can be cancelled.",
                        "payout_not_cancellable")
    payout.status = PayoutStatus.cancelled
    wallet.adjust(db, payout.user_id, payout.amount)
    db.commit()
    db.refresh(payout)
    return payout


def retry(db: Session, payout: Payout) -> Payout:
    """Re-schedule a failed payout: re-reserve the money into a fresh batch."""
    payout = _locked(db, payout)
    if payout.status != PayoutStatus.failed:
        raise _conflict("Only a failed payout can be retried.", "payout_not_retryable")
    user = db.get(User, payout.user_id)
    if user is None or user.wallet_balance < payout.amount:
        raise _conflict("The wallet no longer covers this payout.",
                        "insufficient_wallet_balance")
    today = _now().date()
    payout.status = PayoutStatus.scheduled
    payout.failure_reason = None
    payout.provider_ref = None
    payout.batch_id = f"{batch_id_for(today)}_retry_{uuid.uuid4().hex[:6]}"
    payout.scheduled_for = today
    wallet.adjust(db, payout.user_id, -payout.amount)
    db.commit()
    db.refresh(payout)
    return payout


def get_or_404(db: Session, payout_id: uuid.UUID) -> Payout:
    payout = db.get(Payout, payout_id)
    if payout is None:
        raise NotFoundError("Payout not found.", code="payout_not_found")
    return payout


def list_own(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[Payout]:
    return list(db.scalars(select(Payout).where(Payout.user_id == user_id)
                           .order_by(Payout.created_at.desc()).limit(min(limit, 100))))


def list_admin(db: Session, status: PayoutStatus | None = None,
               batch_id: str | None = None, limit: int = 50) -> list[Payout]:
    stmt = select(Payout)
    if status is not None:
        stmt = stmt.where(Payout.status == status)
    if batch_id:
        stmt = stmt.where(Payout.batch_id == batch_id)
    return list(db.scalars(stmt.order_by(Payout.created_at.desc())
                           .limit(min(limit, 100))))
