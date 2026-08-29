"""Resumable traversal of the nightly sweep populations.

Two of the scheduled jobs recompute every member of a population one record at
a time. That is correct, and it is also unbounded: CI measured the trust sweep
at 82 minutes against ~7,000 users, and no serverless request survives that.

The answer is not to shorten the population — silently recomputing a tenth of
your users while reporting success is worse than not running at all. It is to
traverse the SAME full population across several invocations, in a stable order,
remembering where the last one stopped.

Keyset ordering, not OFFSET: the populations change while the traversal runs
(new users register, reviews get votes), and OFFSET against a moving set both
skips and repeats rows. Ordering by id and resuming from "> last id seen" visits
every row that exists throughout the traversal exactly once, and rows created
mid-traversal are simply picked up by the next period.

The per-record work is unchanged and still real: this module decides WHICH
records a batch covers and in what order, never what is done to them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass
class BatchResult:
    """One invocation's slice of a longer traversal."""

    processed: int
    #: The last key visited, or None when the traversal is finished.
    cursor: str | None
    #: True when the population has been covered end to end.
    complete: bool


def _after(cursor: str | None) -> uuid.UUID | None:
    if not cursor:
        return None
    try:
        return uuid.UUID(cursor)
    except (ValueError, AttributeError):
        # An unreadable cursor restarts the traversal rather than skipping the
        # rest of the population. Repeating work is safe; missing it is not.
        return None


def sweep_trust(db: Session, cursor: str | None, batch: int) -> BatchResult:
    """Recompute trust for the recently-active population, resumably.

    The eligible set is exactly what production has always used —
    `recently_active_user_ids` — with no limit and no sampling. Only the order
    and the stopping point are new.
    """
    from app.services.trust_service import recently_active_user_ids, recompute_user_trust

    eligible = recently_active_user_ids(db)
    if not eligible:
        return BatchResult(processed=0, cursor=None, complete=True)

    after = _after(cursor)
    todo = sorted(eligible, key=lambda u: str(u))
    if after is not None:
        todo = [u for u in todo if str(u) > str(after)]

    slice_ = todo[:batch]
    for user_id in slice_:
        recompute_user_trust(db, user_id)
    db.commit()

    finished = len(slice_) == len(todo)
    return BatchResult(
        processed=len(slice_),
        cursor=None if finished else str(slice_[-1]) if slice_ else cursor,
        complete=finished,
    )


def sweep_wilson(db: Session, cursor: str | None, batch: int) -> BatchResult:
    """Re-decay review Wilson scores, then product trust ratings, resumably.

    The two populations are walked as one sequence — reviews first, then
    products — so a single cursor describes the whole job. The prefix marks
    which half the cursor belongs to, because a bare id could belong to either.
    """
    from app.models.review import Review
    from app.services import trust_rating_service, vote_service

    phase, _, key = (cursor or "").partition(":")
    after = _after(key)

    if phase != "product":
        reviews = sorted(vote_service.voted_review_ids(db), key=str)
        todo = [r for r in reviews if after is None or str(r) > str(after)]
        slice_ = todo[:batch]
        done = 0
        for review_id in slice_:
            review = db.get(Review, review_id)
            if review is None or review.published_at is None or review.is_removed:
                continue
            vote_service.recompute_review_vote_aggregates(db, review)
            done += 1
        db.commit()
        if len(slice_) < len(todo):
            return BatchResult(processed=done, cursor=f"review:{slice_[-1]}",
                               complete=False)
        # Reviews finished; hand over to the product half.
        return BatchResult(processed=done, cursor="product:", complete=False)

    products = sorted(trust_rating_service.reviewed_product_ids(db), key=str)
    todo = [p for p in products if after is None or str(p) > str(after)]
    slice_ = todo[:batch]
    for product_id in slice_:
        trust_rating_service.recompute_product_trust(db, product_id)
    db.commit()

    finished = len(slice_) == len(todo)
    return BatchResult(
        processed=len(slice_),
        cursor=None if finished else f"product:{slice_[-1]}",
        complete=finished,
    )
