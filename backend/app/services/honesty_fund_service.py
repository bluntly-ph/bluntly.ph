"""Honesty Fund monthly distribution (M2 slice 8; FR-6).

Pool = 30% honesty-fund shares of the cycle's commissions. Eligible = published,
not-removed reviews routed to the fund (<=2 stars). Each review's Honesty Score =
trust-weighted helpful votes x price-bracket multiplier (existing pure fns).
Payout_i = pool x score_i / sum(scores), rounded DOWN to the centavo; the dust
remainder stays with the pool (documented). Idempotent per cycle: if the cycle
already has distribution rows, the run ABORTS rather than re-distributing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.commission import Commission
from app.models.enums import (
    EarnEligibleStatus,
    ModerationAction,
    VoteDirection,
)
from app.models.honesty_fund import HonestyFundDistribution
from app.models.moderation import ModerationLog
from app.models.review import Review
from app.models.user import User
from app.models.vote import ReviewVote
from app.services import wallet
from app.services.trust import gate_vote_weight, honesty_score

log = get_logger("honesty_fund")

_CENT = Decimal("0.01")
MANILA = ZoneInfo("Asia/Manila")


def previous_cycle_month(now: datetime | None = None) -> date:
    """First day of the previous calendar month, Asia/Manila."""
    today = (now or datetime.now(UTC)).astimezone(MANILA).date()
    first_of_this = today.replace(day=1)
    last_month = first_of_this - timedelta(days=1)
    return last_month.replace(day=1)


def _review_score(db: Session, review: Review, now: datetime) -> Decimal:
    """Honesty Score: gate-weighted UP votes x price bracket (0 if no votes)."""
    voters = db.execute(
        select(User.trust_stage, User.reputation_score, User.created_at,
               User.is_on_probation)
        .join(ReviewVote, ReviewVote.voter_id == User.id)
        .where(ReviewVote.review_id == review.id,
               ReviewVote.vote == VoteDirection.up)
    ).all()
    weighted = Decimal("0")
    for stage, reputation, created_at, probation in voters:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age_days = max(0, (now - created_at).days)
        weighted += Decimal(str(gate_vote_weight(
            stage, float(reputation), age_days, probation)))
    return honesty_score(weighted, review.price_paid or Decimal("0"))


def distribute(db: Session, cycle_month: date | None = None,
               triggered_by: uuid.UUID | None = None) -> dict:
    cycle = cycle_month or previous_cycle_month()
    now = datetime.now(UTC)

    existing = db.scalar(select(func.count(HonestyFundDistribution.id))
                         .where(HonestyFundDistribution.cycle_month == cycle))
    if existing:
        log.info("honesty fund cycle already distributed; aborting",
                 extra={"extra_fields": {"cycle": str(cycle), "rows": existing}})
        return {"cycle_month": cycle, "pool": "0.00", "recipients": 0,
                "status": "already_distributed"}

    pool = db.scalar(
        select(func.coalesce(func.sum(Commission.honesty_fund_share), 0))
        .where(Commission.cycle_month == cycle)) or Decimal("0")
    pool = Decimal(pool).quantize(_CENT)
    if pool <= 0:
        log.info("honesty fund pool empty; nothing to distribute",
                 extra={"extra_fields": {"cycle": str(cycle)}})
        return {"cycle_month": cycle, "pool": "0.00", "recipients": 0,
                "status": "empty_pool"}

    eligible = db.scalars(
        select(Review).where(
            Review.earn_eligible_status == EarnEligibleStatus.honesty_fund,
            Review.published_at.isnot(None),
            Review.is_removed.is_(False))
    ).all()
    scored = [(r, _review_score(db, r, now)) for r in eligible]
    scored = [(r, s) for r, s in scored if s > 0]
    total_score = sum(s for _, s in scored)
    if not scored or total_score <= 0:
        log.info("no eligible scored reviews for honesty fund cycle",
                 extra={"extra_fields": {"cycle": str(cycle), "pool": str(pool)}})
        return {"cycle_month": cycle, "pool": str(pool), "recipients": 0,
                "status": "no_eligible_reviews"}

    recipients = 0
    for review, score in scored:
        payout = (pool * score / total_score).quantize(_CENT, rounding=ROUND_FLOOR)
        db.add(HonestyFundDistribution(
            distribution_id=f"hfd_{uuid.uuid4().hex[:12]}",
            cycle_month=cycle, review_id=review.id, reviewer_id=review.author_id,
            honesty_score=score, pool_amount=pool, payout_amount=payout,
        ))
        if payout > 0 and review.author_id is not None:
            author = db.get(User, review.author_id)
            wallet.adjust(db, author.id, payout)
        recipients += 1

    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        moderator_id=triggered_by,
        action=ModerationAction.honesty_fund_distribution,
        context={"cycle": str(cycle), "pool": str(pool), "recipients": recipients},
    ))
    db.commit()
    return {"cycle_month": cycle, "pool": str(pool), "recipients": recipients,
            "status": "distributed"}
