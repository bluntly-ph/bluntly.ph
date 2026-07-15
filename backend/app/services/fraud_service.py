"""Fake/shill + collusion fraud signals (M2 slice 5).

ADVISORY ONLY — these signals are surfaced on the moderator queue card and never
auto-block anything (capstone FR-8 invariant). They are computed on read, only
for the queue payload (<= 100 items, 3 bounded queries per item), and are NOT
exposed on any public endpoint.

Deferred (documented, not built): photo pHash reverse-image (needs Supabase
Storage ingestion — M3) and submission-IP capture (privacy assessment first).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import VoteDirection
from app.models.review import Review
from app.models.user import User
from app.models.vote import ReviewVote
from app.services.ranking import (
    COLLUSION_MIN_VOTERS,
    COLLUSION_THRESHOLD,
    velocity_exceeded,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _velocity_flag(db: Session, review_id: uuid.UUID) -> bool:
    """velocity_exceeded over the review's up-votes (>10/h sliding window)."""
    created_ats = db.scalars(
        select(ReviewVote.created_at).where(
            ReviewVote.review_id == review_id,
            ReviewVote.vote == VoteDirection.up)
    ).all()
    now = _now()
    ages = [max(0.0, (now - (c if c.tzinfo else c.replace(tzinfo=UTC))).total_seconds())
            for c in created_ats]
    return velocity_exceeded(ages)


def _collusion_flag(db: Session, review: Review) -> bool:
    """Let V = distinct up-voters of this review, A = its author.
    Flag iff |V| >= 5 AND (|{v in V : A up-voted >= 1 of v's reviews}| / |V|) > 0.6."""
    if review.author_id is None:
        return False
    voters = set(db.scalars(
        select(ReviewVote.voter_id).where(
            ReviewVote.review_id == review.id,
            ReviewVote.vote == VoteDirection.up).distinct()))
    if len(voters) < COLLUSION_MIN_VOTERS:
        return False
    # Authors A has up-voted: which of `voters` authored a review A up-voted?
    reciprocated = set(db.scalars(
        select(Review.author_id)
        .join(ReviewVote, ReviewVote.review_id == Review.id)
        .where(ReviewVote.voter_id == review.author_id,
               ReviewVote.vote == VoteDirection.up,
               Review.author_id.in_(voters))
        .distinct()))
    return (len(reciprocated) / len(voters)) > COLLUSION_THRESHOLD


def _duplicate_content(db: Session, review: Review) -> tuple[bool, uuid.UUID | None]:
    """Best pg_trgm match vs OTHER reviews of the same product or same author."""
    row = db.execute(
        text("""
            SELECT id, similarity(discussion, :body) AS sim
            FROM reviews
            WHERE id <> CAST(:self_id AS uuid)
              AND is_removed = false
              AND (product_id = CAST(:product_id AS uuid)
                   OR (CAST(:author_id AS uuid) IS NOT NULL
                       AND author_id = CAST(:author_id AS uuid)))
              AND similarity(discussion, :body) > :threshold
            ORDER BY sim DESC
            LIMIT 1
        """),
        {"body": review.discussion, "self_id": str(review.id),
         "product_id": str(review.product_id),
         "author_id": str(review.author_id) if review.author_id else None,
         "threshold": settings.duplicate_similarity_threshold},
    ).first()
    if row is None:
        return False, None
    return True, row[0]


def compute_signals(db: Session, review: Review, author: User | None) -> dict:
    """Signals payload for one moderator-queue card."""
    duplicate, duplicate_of = _duplicate_content(db, review)
    account_age_days = 0
    review_count = 0
    if author is not None:
        created = author.created_at if author.created_at.tzinfo \
            else author.created_at.replace(tzinfo=UTC)
        account_age_days = max(0, (_now() - created).days)
        review_count = db.scalar(
            select(func.count(Review.id)).where(
                Review.author_id == author.id, Review.is_removed.is_(False))) or 0
    return {
        "velocity": _velocity_flag(db, review.id),
        "collusion": _collusion_flag(db, review),
        "duplicate_content": duplicate,
        "duplicate_of": str(duplicate_of) if duplicate_of else None,
        "author_account_age_days": account_age_days,
        "author_review_count": review_count,
    }
