"""Resumable traversal of the nightly sweep populations.

Two of the scheduled jobs recompute every member of a population one record at
a time. That is correct, and it is also unbounded: CI measured the trust sweep
at 82 minutes against ~7,000 users, and no serverless request survives that.

The answer is not to shorten the population — silently recomputing a tenth of
your users while reporting success is worse than not running at all. It is to
traverse the SAME full population across several invocations, in a stable
order, remembering where the last one stopped.

WHAT BOUNDS A BATCH. Two things, and the time budget is the one that matters:
a batch stops when it runs out of budget or out of records, whichever comes
first. A record count alone is not a safety property, because per-record cost
is not constant — `recompute_user_trust` does more work for a user with a
thousand votes than for one with none.

WHAT BOUNDS THE RUN. `snapshot_at`, captured once when the logical run is
created. Only rows that existed at that instant are in scope. This is not
decoration: `recently_active_user_ids` keys off `User.updated_at`, and this
sweep writes User rows, so the eligible set is one the job itself perturbs.
Without a fixed boundary a busy database could extend a single run forever.

WHY A TIMESTAMP RATHER THAN "max primary key at run start". These tables use
random UUID primary keys. max(uuid) is not a temporal boundary — a row inserted
after the snapshot sorts below it about half the time, so it would not bound
anything. `created_at <= snapshot_at` does, and it is the same guarantee the
id-based version is reaching for.

ELIGIBILITY, EXACTLY. Not a transaction snapshot, and it should not be
described as one:

  * the population is bounded to rows created at or before `snapshot_at`
  * the selector predicates are re-evaluated when each page is read, so a row
    that stops qualifying before its turn is judged on its current state
  * rows created after `snapshot_at` are not in this run; the next period
    takes them
  * the cursor is an immutable primary key, never a score, vote count or
    timestamp — this job rewrites those, and a cursor the job mutates can skip
    or repeat arbitrary stretches of the population

Keyset ordering, not OFFSET: OFFSET against a set that is changing beneath the
traversal both skips and repeats rows.

The per-record work is unchanged and still real: this module decides WHICH
records a batch covers and in what order, never what is done to them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session


@dataclass
class BatchResult:
    """One invocation's slice of a longer traversal."""

    processed: int
    #: The last key durably completed, or None when the traversal is finished.
    cursor: str | None
    #: True when the population has been covered end to end.
    complete: bool


def _after(cursor: str | None) -> str | None:
    """The key to resume after, or None to start at the beginning."""
    if not cursor:
        return None
    try:
        # Normalise, so a cursor written by another release still compares
        # against `str(id)` the same way.
        return str(uuid.UUID(cursor))
    except (ValueError, AttributeError, TypeError):
        # An unreadable cursor restarts the traversal rather than skipping the
        # rest of the population. Repeating idempotent work is safe; missing it
        # is not.
        return None


def _remaining(ids, after: str | None) -> list[str]:
    """Everything still to visit, in keyset order.

    Sorting the whole eligible set on each call is O(n log n) in Python rather
    than in SQL. At these population sizes that is negligible against the
    per-record recomputation it feeds, and it keeps the selector queries — and
    therefore production eligibility — exactly what they always were.
    """
    ordered = sorted({str(i) for i in ids if i is not None})
    if after is not None:
        ordered = [i for i in ordered if i > after]
    return ordered


def _exhausted(done: int, batch: int, budget) -> bool:
    """Stop on whichever bound is reached first."""
    return done >= batch or (budget is not None and budget.spent())


def sweep_trust(db: Session, cursor: str | None, batch: int,
                snapshot_at: datetime | None = None,
                budget=None) -> BatchResult:
    """Recompute trust for the recently-active population, resumably.

    The eligible set is exactly what production has always used —
    `recently_active_user_ids` — with no limit and no sampling. Only the
    ordering, the boundary and the stopping point are new.
    """
    from app.services.trust_service import recently_active_user_ids, recompute_user_trust

    eligible = recently_active_user_ids(db, created_before=snapshot_at)
    ordered = _remaining(eligible, _after(cursor))
    if not ordered:
        return BatchResult(processed=0, cursor=None, complete=True)

    done = 0
    last: str | None = None
    for user_id in ordered:
        if _exhausted(done, batch, budget):
            break
        recompute_user_trust(db, uuid.UUID(user_id))
        last = user_id
        done += 1
    db.commit()

    finished = done == len(ordered)
    return BatchResult(
        processed=done,
        cursor=None if finished else (last or cursor),
        complete=finished,
    )


def sweep_wilson(db: Session, cursor: str | None, batch: int,
                 snapshot_at: datetime | None = None,
                 budget=None) -> BatchResult:
    """Re-decay review Wilson scores, then product trust ratings, resumably.

    The two populations are walked as one sequence — reviews first, then
    products — so a single cursor describes the whole job. The cursor carries a
    phase prefix because a bare id could belong to either half.
    """
    from app.models.review import Review
    from app.services import trust_rating_service, vote_service

    phase, _, key = (cursor or "review:").partition(":")
    after = _after(key)

    if phase != "product":
        reviews = vote_service.voted_review_ids(db, created_before=snapshot_at)
        ordered = _remaining(reviews, after)
        done = 0
        last: str | None = None
        for review_id in ordered:
            if _exhausted(done, batch, budget):
                break
            review = db.get(Review, uuid.UUID(review_id))
            if review is not None and review.published_at is not None \
                    and not review.is_removed:
                vote_service.recompute_review_vote_aggregates(db, review)
            # Counted and cursored either way: the row was visited, and a row
            # skipped on its merits must not be re-examined by every later
            # invocation.
            last = review_id
            done += 1
        db.commit()

        if done < len(ordered):
            # `last` is None when the budget ran out before the first record.
            # Keeping the incoming cursor matters: writing "review:None" would
            # be unreadable, and an unreadable cursor restarts the traversal —
            # so a persistently tight budget would rewind to the beginning on
            # every call and the sweep would never advance.
            resume = f"review:{last}" if last is not None else (cursor or None)
            return BatchResult(processed=done, cursor=resume, complete=False)
        # Reviews finished; hand the cursor to the product half. NOT complete —
        # half the job remains.
        return BatchResult(processed=done, cursor="product:", complete=False)

    products = trust_rating_service.reviewed_product_ids(db, created_before=snapshot_at)
    ordered = _remaining(products, after)
    if not ordered:
        return BatchResult(processed=0, cursor=None, complete=True)

    done = 0
    last = None
    for product_id in ordered:
        if _exhausted(done, batch, budget):
            break
        trust_rating_service.recompute_product_trust(db, uuid.UUID(product_id))
        last = product_id
        done += 1
    db.commit()

    finished = done == len(ordered)
    # Same guard as the review half: no progress must leave the cursor where it
    # was, never rewind it to the start of the population.
    resume = f"product:{last}" if last is not None else (cursor or "product:")
    return BatchResult(
        processed=done,
        cursor=None if finished else resume,
        complete=finished,
    )
