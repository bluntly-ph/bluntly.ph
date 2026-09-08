"""Fake/shill + collusion fraud signals (M2 slice 5).

ADVISORY ONLY — these signals are surfaced on the moderator queue card and never
auto-block anything (capstone FR-8 invariant). They are computed on read in
bounded batches and are NOT exposed on any public endpoint.

Deferred (documented, not built): photo pHash reverse-image (needs Supabase
Storage ingestion — M3) and submission-IP capture (privacy assessment first).
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Iterator, Mapping
from datetime import UTC, datetime

from sqlalchemy import bindparam, func, select, text
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


_QUERY_CHUNK_SIZE = 500


def _chunks(values: Collection[uuid.UUID]) -> Iterator[tuple[uuid.UUID, ...]]:
    items = tuple(dict.fromkeys(values))
    for start in range(0, len(items), _QUERY_CHUNK_SIZE):
        yield items[start : start + _QUERY_CHUNK_SIZE]


_DUPLICATES_FOR_REVIEWS = text(
    """
    SELECT target.id AS review_id, duplicate.id AS duplicate_of
    FROM reviews AS target
    JOIN LATERAL (
        SELECT candidate.id
        FROM reviews AS candidate
        WHERE candidate.id <> target.id
          AND candidate.is_removed = false
          AND (
              candidate.product_id = target.product_id
              OR (target.author_id IS NOT NULL AND candidate.author_id = target.author_id)
          )
          AND similarity(candidate.discussion, target.discussion) > :threshold
        ORDER BY similarity(candidate.discussion, target.discussion) DESC
        LIMIT 1
    ) AS duplicate ON true
    WHERE target.id IN :review_ids
    """
).bindparams(bindparam("review_ids", expanding=True))


def compute_signals_by_review(
    db: Session,
    reviews: Collection[Review],
    authors: Mapping[uuid.UUID, User],
    *,
    now: datetime | None = None,
) -> dict[uuid.UUID, dict]:
    """Compute the existing six advisory fields for a review batch.

    Each fact source is queried once per bounded chunk, so evaluating a global
    queue does not add four or five round trips for every candidate. The
    collusion definition and duplicate threshold are identical to the original
    one-review implementation; only acquisition is batched.
    """
    review_by_id = {review.id: review for review in reviews}
    if not review_by_id:
        return {}

    evaluated_at = now or _now()
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=UTC)
    else:
        evaluated_at = evaluated_at.astimezone(UTC)

    review_ids = tuple(review_by_id)
    vote_times: dict[uuid.UUID, list[datetime]] = {}
    voters: dict[uuid.UUID, set[uuid.UUID]] = {}
    for chunk in _chunks(review_ids):
        rows = db.execute(
            select(ReviewVote.review_id, ReviewVote.voter_id, ReviewVote.created_at).where(
                ReviewVote.review_id.in_(chunk),
                ReviewVote.vote == VoteDirection.up,
            )
        ).all()
        for review_id, voter_id, created_at in rows:
            vote_times.setdefault(review_id, []).append(created_at)
            voters.setdefault(review_id, set()).add(voter_id)

    author_ids = {
        review.author_id
        for review in review_by_id.values()
        if review.author_id is not None
    }
    reciprocated_by_author: dict[uuid.UUID, set[uuid.UUID]] = {}
    author_review_counts: dict[uuid.UUID, int] = {}
    for chunk in _chunks(author_ids):
        reciprocal_rows = db.execute(
            select(ReviewVote.voter_id, Review.author_id)
            .join(Review, ReviewVote.review_id == Review.id)
            .where(
                ReviewVote.voter_id.in_(chunk),
                ReviewVote.vote == VoteDirection.up,
                Review.author_id.is_not(None),
            )
            .distinct()
        ).all()
        for author_id, reciprocated_author_id in reciprocal_rows:
            reciprocated_by_author.setdefault(author_id, set()).add(
                reciprocated_author_id
            )

        count_rows = db.execute(
            select(Review.author_id, func.count(Review.id))
            .where(
                Review.author_id.in_(chunk),
                Review.is_removed.is_(False),
            )
            .group_by(Review.author_id)
        ).all()
        author_review_counts.update(
            (author_id, int(count)) for author_id, count in count_rows
        )

    duplicate_of: dict[uuid.UUID, uuid.UUID] = {}
    for chunk in _chunks(review_ids):
        rows = db.execute(
            _DUPLICATES_FOR_REVIEWS,
            {
                "review_ids": chunk,
                "threshold": settings.duplicate_similarity_threshold,
            },
        ).all()
        duplicate_of.update(rows)

    signals_by_review: dict[uuid.UUID, dict] = {}
    for review_id, review in review_by_id.items():
        ages = [
            max(
                0.0,
                (
                    evaluated_at
                    - (created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC))
                ).total_seconds(),
            )
            for created_at in vote_times.get(review_id, ())
        ]
        review_voters = voters.get(review_id, set())
        collusion = False
        if review.author_id is not None and len(review_voters) >= COLLUSION_MIN_VOTERS:
            reciprocated = review_voters & reciprocated_by_author.get(
                review.author_id, set()
            )
            collusion = (len(reciprocated) / len(review_voters)) > COLLUSION_THRESHOLD

        author = authors.get(review.author_id) if review.author_id is not None else None
        account_age_days = 0
        if author is not None:
            created = (
                author.created_at
                if author.created_at.tzinfo
                else author.created_at.replace(tzinfo=UTC)
            )
            account_age_days = max(0, (evaluated_at - created).days)

        duplicate_id = duplicate_of.get(review_id)
        signals_by_review[review_id] = {
            "velocity": velocity_exceeded(ages),
            "collusion": collusion,
            "duplicate_content": duplicate_id is not None,
            "duplicate_of": str(duplicate_id) if duplicate_id else None,
            "author_account_age_days": account_age_days,
            "author_review_count": author_review_counts.get(review.author_id, 0),
        }
    return signals_by_review


def compute_signals(
    db: Session,
    review: Review,
    author: User | None,
    *,
    now: datetime | None = None,
) -> dict:
    """Signals payload for one moderator-queue card."""
    authors = {author.id: author} if author is not None else {}
    return compute_signals_by_review(db, [review], authors, now=now)[review.id]
