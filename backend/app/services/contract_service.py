"""Monetized-review contracts (M3 slice 10).

One contract per monetized review. Its single economic effect lives at
reconciliation: `reviewer_bps_for_review()` returns the reviewer's tier bps while
the contract is `active`, and **0** once it is `expired` / `bought_out` / absent.
The Honesty Fund's fixed 30% is never affected — only the reviewer's share moves,
and the platform absorbs the difference.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, NotFoundError
from app.models.contract import ReviewContract
from app.models.enums import ContractStatus, ModerationAction, ModerationTargetType
from app.models.moderation import ModerationLog
from app.models.review import Review
from app.models.user import User
from app.services import wallet


def _now() -> datetime:
    return datetime.now(UTC)


def _conflict(detail: str, code: str) -> AppError:
    return AppError(detail, code=code, status_code=409, title="Conflicting state")


def get_active_contract(db: Session, review_id: uuid.UUID) -> ReviewContract | None:
    return db.scalar(select(ReviewContract).where(
        ReviewContract.review_id == review_id,
        ReviewContract.status == ContractStatus.active))


def ensure_contract(db: Session, review: Review) -> ReviewContract | None:
    """Called when a review first becomes monetized. Re-attaching a link after a
    revoke REUSES the existing active contract rather than starting a new term."""
    if review.author_id is None:
        return None
    existing = get_active_contract(db, review.id)
    if existing is not None:
        return existing
    now = _now()
    contract = ReviewContract(
        review_id=review.id, reviewer_id=review.author_id,
        status=ContractStatus.active, started_at=now,
        term_months=settings.contract_term_months,
        expires_at=now + relativedelta(months=settings.contract_term_months),
        auto_renew=True, renewal_count=0,
    )
    db.add(contract)
    db.flush()
    return contract


def reviewer_bps_for_review(db: Session, review_id: uuid.UUID,
                            tier_bps: int) -> tuple[int, ContractStatus | None]:
    """The single integration point with the M2 slice-6 split.

    Returns (effective reviewer bps, contract status snapshot). No active
    contract -> 0 bps: the reviewer's share stops, the platform takes it.
    """
    contract = db.scalar(select(ReviewContract).where(
        ReviewContract.review_id == review_id).order_by(
        ReviewContract.created_at.desc()))
    if contract is None:
        return 0, None
    if contract.status == ContractStatus.active:
        return tier_bps, ContractStatus.active
    return 0, contract.status


def sweep_contracts(db: Session) -> dict[str, int]:
    """Daily: active contracts past term either auto-renew or expire."""
    due = db.scalars(select(ReviewContract).where(
        ReviewContract.status == ContractStatus.active,
        ReviewContract.expires_at <= _now())).all()
    renewed = expired = 0
    for contract in due:
        if contract.auto_renew:
            contract.expires_at = contract.expires_at + relativedelta(
                months=contract.term_months)
            contract.renewal_count += 1
            renewed += 1
        else:
            contract.status = ContractStatus.expired
            # An expiring contract voids any pending buyout offer.
            contract.buyout_offer_amount = None
            contract.buyout_offered_at = None
            expired += 1
    db.commit()
    return {"renewed": renewed, "expired": expired}


def get_or_404(db: Session, contract_id: uuid.UUID) -> ReviewContract:
    contract = db.get(ReviewContract, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found.", code="contract_not_found")
    return contract


def _require_owner(contract: ReviewContract, user: User) -> None:
    if contract.reviewer_id != user.id:
        raise AppError("This is not your contract.", code="not_contract_owner",
                       status_code=403, title="Insufficient permissions")



def _locked(db: Session, contract: ReviewContract) -> ReviewContract:
    """Re-read a contract FOR UPDATE so its state check cannot race.

    `accept_buyout` reads `status`, decides, credits a wallet, then writes the
    new status. Read outside a lock, two concurrent accepts both see `active`,
    both pass the guard, and both credit the buyout amount - the reviewer is
    paid twice for one contract, and nothing anywhere reports it.

    The same shape as payout_service._locked, and for the same reason:
    "only an active contract can be bought out" reads like a state machine
    while behaving like a suggestion. `populate_existing` matters - without it
    the identity map returns the same instance that was just checked and the
    lock buys nothing.
    """
    return db.execute(
        select(ReviewContract)
        .where(ReviewContract.id == contract.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def set_auto_renew(db: Session, contract: ReviewContract, user: User,
                   auto_renew: bool) -> ReviewContract:
    _require_owner(contract, user)
    contract = _locked(db, contract)
    if contract.status != ContractStatus.active:
        raise _conflict("Only an active contract can change its renewal setting.",
                        "contract_not_active")
    contract.auto_renew = auto_renew
    db.commit()
    db.refresh(contract)
    return contract


def offer_buyout(db: Session, contract: ReviewContract, moderator_id: uuid.UUID,
                 amount: Decimal) -> ReviewContract:
    contract = _locked(db, contract)
    if contract.status != ContractStatus.active:
        raise _conflict("Only an active contract can be bought out.",
                        "contract_not_active")
    if contract.buyout_offer_amount is not None:
        raise _conflict("This contract already has a pending buyout offer.",
                        "buyout_already_pending")
    if amount <= 0:
        raise AppError("Buyout amount must be positive.", code="invalid_buyout_amount",
                       status_code=422, title="Invalid amount")
    contract.buyout_offer_amount = amount
    contract.buyout_offered_at = _now()
    contract.buyout_offered_by = moderator_id
    contract.buyout_rejected_at = None
    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        target_type=ModerationTargetType.review, target_ref=contract.review_id,
        moderator_id=moderator_id, action=ModerationAction.override,
        notes="buyout offered",
        context={"contract_id": str(contract.id), "amount": str(amount)},
    ))
    db.commit()
    db.refresh(contract)
    return contract


def accept_buyout(db: Session, contract: ReviewContract, user: User) -> ReviewContract:
    _require_owner(contract, user)
    contract = _locked(db, contract)
    if contract.status != ContractStatus.active:
        raise _conflict("Only an active contract can be bought out.",
                        "contract_not_active")
    if contract.buyout_offer_amount is None:
        raise _conflict("There is no pending buyout offer.", "no_pending_buyout")
    amount = contract.buyout_offer_amount
    reviewer = db.get(User, user.id)
    wallet.adjust(db, reviewer.id, amount)
    contract.status = ContractStatus.bought_out
    contract.buyout_accepted_at = _now()
    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        target_type=ModerationTargetType.review, target_ref=contract.review_id,
        moderator_id=contract.buyout_offered_by, action=ModerationAction.override,
        notes="buyout accepted",
        context={"contract_id": str(contract.id), "amount": str(amount),
                 "reviewer_id": str(user.id)},
    ))
    db.commit()
    db.refresh(contract)
    return contract


def reject_buyout(db: Session, contract: ReviewContract, user: User) -> ReviewContract:
    _require_owner(contract, user)
    contract = _locked(db, contract)
    if contract.buyout_offer_amount is None:
        raise _conflict("There is no pending buyout offer.", "no_pending_buyout")
    contract.buyout_offer_amount = None
    contract.buyout_offered_at = None
    contract.buyout_rejected_at = _now()
    db.commit()
    db.refresh(contract)
    return contract


def list_own(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[ReviewContract]:
    return list(db.scalars(
        select(ReviewContract).where(ReviewContract.reviewer_id == user_id)
        .order_by(ReviewContract.created_at.desc()).limit(min(limit, 100))))


def list_admin(db: Session, status: ContractStatus | None = None,
               expiring_within_days: int | None = None,
               limit: int = 50) -> list[ReviewContract]:
    from datetime import timedelta

    stmt = select(ReviewContract)
    if status is not None:
        stmt = stmt.where(ReviewContract.status == status)
    if expiring_within_days is not None:
        stmt = stmt.where(
            ReviewContract.status == ContractStatus.active,
            ReviewContract.expires_at <= _now() + timedelta(days=expiring_within_days))
    return list(db.scalars(stmt.order_by(ReviewContract.expires_at.asc())
                           .limit(min(limit, 100))))
