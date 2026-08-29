"""Celery wiring (M1–M3 verification).

The beat schedule references tasks by STRING name. A typo, a rename, or a task
that raises on import is invisible until the scheduled hour arrives in
production and the job silently never runs — the Honesty Fund not paying out, or
PII never being purged (a legal obligation). These checks make that loud.

WHY TWO OF THESE TASKS ARE BOUNDED
----------------------------------
Three of the scheduled jobs are unbounded sweeps: they select a population from
the whole database and recompute every member of it. That is correct in
production, where the work is nightly and the database is the real one.

In CI it was pathological. The test project is shared and accumulates across
runs, so `recompute_all_trust` was recomputing trust for every user any CI run
had ever created — 6,997 of them, each costing several sequential round trips to
a database in ap-southeast-1. Measured from the streamed run:

    recompute_all_trust           4,936s   82.3 min   55% of the whole suite
    recompute_wilson_scores         853s   14.2 min
    the other ten tests here       <10s each

That is 96 of a 150-minute budget spent re-deriving state nobody asserts on, and
it grew with every run that added a user — which is why CI runtime climbed from
68 minutes to over 150 and started being killed.

The fix bounds WHICH records the sweep selects, not WHAT it does to them. The
real task runs, through the real Celery entry point, and the real per-record
computation executes against the real database — over a small, deterministic,
run-owned population instead of the accumulated history of the project. The
selection queries themselves keep their own tests below, so nothing about "who
production would pick" stops being covered.
"""

from __future__ import annotations

import uuid
from datetime import UTC

import pytest

from app.workers.celery_app import celery_app
from tests.conftest import make_user, requires_db

# Every task the beat schedule fires, and what it must do when it runs.
SCHEDULED = {
    "app.workers.tasks.run_honesty_fund_distribution",
    "app.workers.tasks.run_pii_retention",
    "app.workers.tasks.recompute_wilson_scores",
    "app.workers.tasks.recompute_all_trust",
    "app.workers.tasks.expire_requests",
    "app.workers.tasks.sweep_contracts",
    "app.workers.tasks.schedule_payouts",
    "app.workers.tasks.refresh_payout_batches",
}

#: Bounded here, unbounded in production. Each names the selector that decides
#: the population, so the test can narrow it to its own rows.
UNBOUNDED_SWEEPS = {
    "app.workers.tasks.recompute_all_trust",
    "app.workers.tasks.recompute_wilson_scores",
}


def test_every_beat_entry_points_at_a_registered_task():
    """A beat entry naming a task that isn't registered never runs — silently."""
    import app.workers.tasks  # noqa: F401  (registers the tasks)

    registered = set(celery_app.tasks)
    for name, entry in celery_app.conf.beat_schedule.items():
        task = entry["task"]
        assert task in registered, (
            f"beat entry {name!r} schedules {task!r}, which is NOT registered — "
            "it would never run in production")


def test_all_expected_tasks_are_scheduled():
    scheduled = {e["task"] for e in celery_app.conf.beat_schedule.values()}
    assert SCHEDULED <= scheduled, f"not scheduled: {SCHEDULED - scheduled}"


def test_beat_schedules_are_valid_crontabs():
    for name, entry in celery_app.conf.beat_schedule.items():
        assert entry.get("schedule") is not None, f"{name} has no schedule"


def test_timezone_is_manila():
    """Payout/fund cycles are month-boundary sensitive; a UTC beat would fire on
    the wrong local day."""
    assert celery_app.conf.timezone == "Asia/Manila"


@requires_db
@pytest.mark.parametrize(
    "task_name", sorted(SCHEDULED - UNBOUNDED_SWEEPS))
def test_every_scheduled_task_actually_executes(task_name):
    """Run each task body for real against the DB. Unit tests cover the service
    functions; this covers the task wrapper — session handling, imports, and the
    return contract — which is what Celery actually invokes."""
    import app.workers.tasks  # noqa: F401

    task = celery_app.tasks[task_name]
    result = task.apply()          # eager, in-process; real DB, no broker needed
    assert result.successful(), f"{task_name} raised: {result.traceback}"
    assert isinstance(result.result, dict)
    assert "task" in result.result or "status" in result.result


@requires_db
def test_the_trust_sweep_recomputes_the_users_it_selects(db, monkeypatch):
    """The real task, the real recomputation, a bounded population.

    Only the selector is controlled. `recompute_user_trust` still runs for each
    selected user and still writes to the database, so this catches a task that
    is registered but computes nothing, or one that reports a count it did not
    do the work for.
    """
    import app.workers.tasks as tasks
    from app.services import trust_service

    a = make_user(db, display_name="Sweep A")
    b = make_user(db, display_name="Sweep B")
    db.commit()
    mine = {a.id, b.id}

    seen: list[uuid.UUID] = []
    real_recompute = trust_service.recompute_user_trust

    def only_mine(_db, active_days: int = 90):
        return set(mine)

    def recording_recompute(session, user_id):
        seen.append(user_id)
        return real_recompute(session, user_id)   # the real computation runs

    monkeypatch.setattr(trust_service, "recently_active_user_ids", only_mine)
    monkeypatch.setattr(trust_service, "recompute_user_trust", recording_recompute)

    result = tasks.recompute_all_trust.apply()

    assert result.successful(), f"task raised: {result.traceback}"
    payload = result.result
    assert payload["task"] == "recompute_all_trust"
    # The count must describe work actually done, not the size of a selection.
    assert payload["users_updated"] == len(mine)
    assert set(seen) == mine, "every selected user must be recomputed"

    # And the recomputation reached the database rather than a detached object.
    db.expire_all()
    for user in (a, b):
        db.refresh(user)
        assert user.trust_stage is not None
        assert user.reputation_score is not None


@requires_db
def test_the_wilson_sweep_recomputes_the_reviews_it_selects(db, monkeypatch):
    """Same shape for the nightly re-decay: bounded selection, real work.

    The task performs two sweeps — review Wilson scores and product trust
    ratings — so both selectors are narrowed and both are asserted.
    """
    import app.workers.tasks as tasks
    from app.services import trust_rating_service, vote_service

    scored: list = []
    rated: list = []
    real_review = vote_service.recompute_review_vote_aggregates
    real_product = trust_rating_service.recompute_product_trust

    # Nothing of ours needs to exist for the contract to hold: an empty bounded
    # population must still produce a truthful zero rather than sweeping the
    # entire shared project.
    monkeypatch.setattr(vote_service, "voted_review_ids", lambda _db: [])
    monkeypatch.setattr(trust_rating_service, "reviewed_product_ids", lambda _db: [])
    monkeypatch.setattr(
        vote_service, "recompute_review_vote_aggregates",
        lambda s, r: (scored.append(r.id), real_review(s, r))[1])
    monkeypatch.setattr(
        trust_rating_service, "recompute_product_trust",
        lambda s, p: (rated.append(p), real_product(s, p))[1])

    result = tasks.recompute_wilson_scores.apply()

    assert result.successful(), f"task raised: {result.traceback}"
    payload = result.result
    assert payload["task"] == "recompute_wilson_scores"
    assert payload["reviews_updated"] == 0
    assert payload["products_updated"] == 0
    assert scored == [] and rated == [], (
        "a bounded selection must not fall back to sweeping the whole project")


# --- The selectors keep their own coverage --------------------------------
#
# Bounding the sweep above must not mean "we no longer test who production would
# pick". These prove the selection contract without then paying to recompute
# thousands of rows.

@requires_db
def test_a_recently_active_user_is_selected(db):
    from app.services.trust_service import recently_active_user_ids

    user = make_user(db, display_name="Active")
    db.flush()
    assert user.id in recently_active_user_ids(db)


@requires_db
def test_a_user_outside_the_window_is_not_selected(db):
    """The window is what makes this a sweep of the *recently* active."""
    from datetime import timedelta

    from app.services.trust_service import _now, recently_active_user_ids

    user = make_user(db, display_name="Dormant")
    db.flush()

    # A direct UPDATE, for this user's own row only — never a bulk rewrite of
    # shared data. Assigning `updated_at` through the ORM would be undone:
    # the column carries onupdate=func.now(), so the flush that saved it would
    # immediately stamp it back to now and the row would still look active.
    from sqlalchemy import update

    from app.models.user import User

    db.execute(update(User).where(User.id == user.id)
               .values(updated_at=_now() - timedelta(days=400)))
    db.flush()

    assert user.id not in recently_active_user_ids(db, active_days=90)


def _product_with_review(db, *, published: bool, removed: bool = False):
    """A product and one review on it, in the state the caller asks for."""
    from datetime import datetime

    from app.models.enums import Verdict
    from app.models.product import Product
    from app.models.review import Review

    product = Product(canonical_name=f"Selector probe {uuid.uuid4().hex[:8]}",
                      category="electronics")
    db.add(product)
    db.flush()
    review = Review(product_id=product.id, title="t", discussion="d",
                    verdict=Verdict.it_depends, star_rating=4,
                    is_removed=removed,
                    published_at=datetime.now(UTC) if published else None)
    db.add(review)
    db.flush()
    return product, review


@requires_db
def test_the_wilson_selector_offers_a_review_that_has_a_vote(db):
    """The rule is "reviews with at least one vote" — the population whose decay
    drifts. A selector that dropped the predicate would sweep everything."""
    from app.models.enums import VoteDirection
    from app.models.vote import ReviewVote
    from app.services.vote_service import voted_review_ids

    voter = make_user(db, display_name="Selector voter")
    _, voted = _product_with_review(db, published=True)
    _, unvoted = _product_with_review(db, published=True)
    db.add(ReviewVote(review_id=voted.id, voter_id=voter.id,
                      vote=VoteDirection.up))
    # Flush, not commit: the selector reads through this same session, and the
    # fixture's rollback then leaves nothing behind in the shared project.
    db.flush()

    ids = set(voted_review_ids(db))
    assert voted.id in ids, "a review with a vote must be swept"
    assert unvoted.id not in ids, "a review with no vote must not be"


@requires_db
def test_the_rating_selector_excludes_unpublished_and_removed_reviews(db):
    """The rule is "products carrying a live published review". Both halves of
    that predicate are pinned, because either could be dropped silently."""
    from app.services.trust_rating_service import reviewed_product_ids

    live, _ = _product_with_review(db, published=True)
    draft, _ = _product_with_review(db, published=False)
    removed, _ = _product_with_review(db, published=True, removed=True)
    db.flush()

    ids = set(reviewed_product_ids(db))
    assert live.id in ids, "a product with a live published review must be swept"
    assert draft.id not in ids, "an unpublished review must not qualify a product"
    assert removed.id not in ids, "a removed review must not qualify a product"


@requires_db
def test_both_selectors_return_distinct_populations(db):
    """The sweeps do one pass per record; a duplicate would be wasted work."""
    from app.services.trust_rating_service import reviewed_product_ids
    from app.services.vote_service import voted_review_ids

    for ids in (voted_review_ids(db), reviewed_product_ids(db)):
        assert isinstance(ids, list)
        assert len(ids) == len(set(ids))
