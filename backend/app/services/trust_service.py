"""Trust progression wiring (M2 slice 3).

Recomputes a user's reputation_score / trust_stage from their actual review and
vote history using the pure ADR-003 functions, and awards stage badges. Stages
move ONLY through this recompute — there is no manual stage-set endpoint.

Triggers: review publish/unpublish/reject (referral_service), vote writes
(vote_service), and the nightly `recompute_all_trust` Celery sweep.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import VerificationStatus
from app.models.review import Review
from app.models.user import Badge, User, UserBadge
from app.models.vote import ReviewVote
from app.services.trust import (
    determine_stage,
    evidence_capped_stage,
    helpfulness_score,
    reputation_score,
)

# trust_stage -> seeded badge_id awarded on reaching it (no removal on drop).
STAGE_BADGES = {
    2: "verified_buyer",
    3: "established_reviewer",
    4: "trusted_reviewer",
    5: "community_expert",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _award_stage_badges(db: Session, user: User, old_stage: int, new_stage: int) -> None:
    for stage in range(max(2, old_stage + 1), new_stage + 1):
        code = STAGE_BADGES.get(stage)
        if code is None:
            continue
        badge = db.scalar(select(Badge).where(Badge.badge_id == code))
        if badge is None:
            continue  # badge not seeded in this environment
        already = db.scalar(select(UserBadge.id).where(
            UserBadge.user_id == user.id, UserBadge.badge_id == badge.id))
        if already is None:
            db.add(UserBadge(user_id=user.id, badge_id=badge.id))


def recompute_user_trust(db: Session, user_id: uuid.UUID) -> None:
    """Recompute reputation inputs -> score -> stage -> badges. Does NOT commit;
    runs inside the caller's transaction (vote write / publish / sweep).

    Sessions run with autoflush=False: flush so the SELECTs below see the
    caller's pending writes (vote counters, published_at, ...).
    """
    db.flush()
    user = db.get(User, user_id)
    if user is None:
        return

    published = Review.published_at.isnot(None) & Review.is_removed.is_(False)
    review_count, verified_count = db.execute(
        select(
            func.count(Review.id),
            func.count(Review.id).filter(
                Review.verification_status == VerificationStatus.verified),
        ).where(Review.author_id == user_id, published)
    ).one()

    helpful, unhelpful = db.execute(
        select(func.coalesce(func.sum(Review.helpful_votes), 0),
               func.coalesce(func.sum(Review.unhelpful_votes), 0))
        .where(Review.author_id == user_id, published)
    ).one()
    total_votes = helpful + unhelpful
    helpfulness = helpfulness_score(helpful, unhelpful)

    created_at = user.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    months_active = (_now() - created_at).days / 30

    user.verified_review_count = verified_count
    user.helpfulness_ratio = helpfulness
    user.reputation_score = round(reputation_score(
        helpfulness_ratio=helpfulness,
        verified_review_count=verified_count,
        best_answer_count=user.best_answer_count,
        strikes=user.strikes,
    ), 2)

    old_stage = user.trust_stage
    new_stage = evidence_capped_stage(
        determine_stage(
            review_count=review_count,
            verified_review_count=verified_count,
            helpfulness_ratio=helpfulness,
            best_answer_count=user.best_answer_count,
            strikes=user.strikes,
            months_active=months_active,
        ),
        total_votes=total_votes,
    )
    user.trust_stage = new_stage
    if new_stage > old_stage:
        _award_stage_badges(db, user, old_stage, new_stage)


def recently_active_user_ids(db: Session, active_days: int = 90) -> set:
    """Who the nightly sweep considers active: profile touched, review written,
    or vote cast within `active_days`.

    Split out from the sweep so the selection can be named and tested on its
    own. It is the same query the sweep has always run.
    """
    cutoff = _now() - timedelta(days=active_days)
    user_ids = set(db.scalars(
        select(User.id).where(User.updated_at >= cutoff)))
    user_ids.update(db.scalars(
        select(Review.author_id).where(Review.created_at >= cutoff,
                                       Review.author_id.isnot(None)).distinct()))
    user_ids.update(db.scalars(
        select(ReviewVote.voter_id).where(ReviewVote.created_at >= cutoff).distinct()))
    return user_ids


def recompute_recently_active_users(db: Session, active_days: int = 90) -> int:
    """Nightly sweep: recompute trust for users active in the last `active_days`
    (profile updated, authored a review, or cast a vote). Commits once."""
    user_ids = recently_active_user_ids(db, active_days)
    for user_id in user_ids:
        recompute_user_trust(db, user_id)
    db.commit()
    return len(user_ids)
