"""Community visibility voting on published reviews (M2 slice 2).

Equal-weight up/down votes feed the time-decayed Wilson score (ADR-004, 45d
half-life) that ranks listings, and the author's helpfulness_ratio that feeds
trust progression. All aggregate updates happen in the same transaction as the
vote write so counters can never drift from the vote rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.models.enums import VoteDirection
from app.models.review import Review
from app.models.user import User
from app.models.vote import ReviewVote
from app.services.ranking import time_decayed_wilson


def _now() -> datetime:
    return datetime.now(UTC)


def age_days(created_at: datetime, now: datetime | None = None) -> float:
    now = now or _now()
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return max(0.0, (now - created_at).total_seconds() / 86400.0)


def recompute_review_vote_aggregates(db: Session, review: Review) -> None:
    """Refresh helpful/unhelpful counts + time-decayed wilson from the vote rows."""
    votes = list(db.execute(
        select(ReviewVote.vote, ReviewVote.created_at)
        .where(ReviewVote.review_id == review.id)
    ))
    now = _now()
    review.helpful_votes = sum(1 for v, _ in votes if v == VoteDirection.up)
    review.unhelpful_votes = len(votes) - review.helpful_votes
    review.wilson_score = time_decayed_wilson(
        (v == VoteDirection.up, age_days(created, now)) for v, created in votes
    )


def _votable_or_404(review: Review) -> None:
    if review.published_at is None or review.is_removed:
        raise NotFoundError("Review not found.", code="review_not_found")


def cast_vote(db: Session, review: Review, voter: User,
              direction: VoteDirection) -> Review:
    _votable_or_404(review)
    if review.author_id == voter.id:
        raise AppError("You cannot vote on your own review.",
                       code="cannot_vote_own_review", status_code=409,
                       title="Conflicting state")

    existing = db.scalar(select(ReviewVote).where(
        ReviewVote.review_id == review.id, ReviewVote.voter_id == voter.id))
    if existing is None:
        db.add(ReviewVote(review_id=review.id, voter_id=voter.id, vote=direction))
    else:
        existing.vote = direction
    try:
        db.flush()
    except IntegrityError as exc:  # concurrent first-votes hit uq_review_vote_once
        db.rollback()
        raise AppError("Your vote was submitted twice at once; retry.",
                       code="vote_conflict", status_code=409,
                       title="Conflicting state") from exc
    _finish_vote_write(db, review)
    return review


def remove_vote(db: Session, review: Review, voter_id: uuid.UUID) -> Review:
    _votable_or_404(review)
    existing = db.scalar(select(ReviewVote).where(
        ReviewVote.review_id == review.id, ReviewVote.voter_id == voter_id))
    if existing is None:
        raise NotFoundError("You have no vote on this review.", code="vote_not_found")
    db.delete(existing)
    db.flush()
    _finish_vote_write(db, review)
    return review


def _finish_vote_write(db: Session, review: Review) -> None:
    """Shared tail of every vote mutation — one transaction end to end.

    Trust recompute (slice 3) also refreshes the author's helpfulness_ratio from
    the just-updated review counters (it flushes before reading — sessions run
    with autoflush=False).
    """
    recompute_review_vote_aggregates(db, review)
    if review.author_id is not None:
        from app.services.trust_service import recompute_user_trust
        recompute_user_trust(db, review.author_id)
    db.commit()
    db.refresh(review)


def voted_review_ids(db: Session, created_before=None) -> list:
    """Reviews with at least one vote — the population the nightly re-decay
    walks. Named so the selection can be tested and bounded independently of
    the recomputation it feeds.

    `created_before` defaults to None (the historical behaviour). The resumable
    scheduler passes the instant its logical run began, so a traversal spread
    over several requests has a fixed population; reviews created after it are
    picked up by the next period.
    """
    stmt = select(ReviewVote.review_id)
    if created_before is not None:
        stmt = stmt.join(Review, Review.id == ReviewVote.review_id).where(
            Review.created_at <= created_before)
    return list(db.scalars(stmt.distinct()).all())


def recompute_all_wilson_scores(db: Session) -> int:
    """Nightly sweep: re-decay wilson for published reviews with >=1 vote.

    Decay drifts with time even without new votes, so listings would go stale
    without this. Returns the number of reviews updated.
    """
    review_ids = voted_review_ids(db)
    updated = 0
    for review_id in review_ids:
        review = db.get(Review, review_id)
        if review is None or review.published_at is None or review.is_removed:
            continue
        recompute_review_vote_aggregates(db, review)
        updated += 1
    db.commit()
    return updated
