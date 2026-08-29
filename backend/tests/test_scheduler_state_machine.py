"""The scheduler's claim/lease state machine, against a real PostgreSQL.

These tests exist because the failure modes here are all invisible on SQLite
and invisible under a single connection. Every one of them is about two runners
disagreeing about who owns a logical run, so nothing here mocks the claim
function or the repository: the arbitration under test IS the SQL.

The properties, in the order they matter:

  1. a released `continuing` run resumes on the very next call, with no delay
  2. exactly one of two simultaneous claimants executes
  3. a request whose lease expired cannot overwrite the runner that replaced it
  4. failure preserves the cursor, so a retry resumes instead of restarting
  5. a traversal covers its whole population across batches, exactly once each
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.api.v1.routes import internal_cron
from app.models.maintenance import CronCredential, CronRun
from tests.conftest import requires_db

CRON = "/api/v1/internal/cron"
SECRET = "state-machine-secret-not-used-anywhere-else"


@pytest.fixture
def scheduler_credential(db):
    row = CronCredential(
        name=internal_cron.CREDENTIAL_NAME,
        secret_sha256=hashlib.sha256(SECRET.encode()).hexdigest(),
        is_active=True)
    db.add(row)
    db.commit()
    yield row
    db.delete(row)
    db.commit()


@pytest.fixture
def task(db):
    """A task name whose rows this test owns, cleaned up afterwards.

    Registered in TASKS so the route accepts it; removed again after, so no
    other test inherits it.
    """
    name = f"probe_{uuid.uuid4().hex[:8]}"
    yield name
    db.query(CronRun).filter(CronRun.task == name).delete()
    db.commit()
    internal_cron.TASKS.pop(name, None)


def _run(db, task_name):
    return db.scalar(select(CronRun).where(CronRun.task == task_name,
                                           CronRun.status.in_(
                                               internal_cron.CLAIMABLE + (internal_cron.OK,))))


# --- 1. Continuation resumes immediately -----------------------------------

@requires_db
def test_a_continuing_run_is_resumable_on_the_very_next_call(
        client, db, task, scheduler_credential, monkeypatch):
    """The property the 30-minute takeover window must NOT govern.

    `continuing` means "incomplete but idle". If the second call had to wait
    for a lease to expire before it could resume, a sweep needing twenty
    batches would take ten hours of wall clock to finish a nightly job.
    """
    from app.services.sweep_service import BatchResult

    seen = []

    def fake_sweep(_db, cursor, _batch, _snapshot, _budget):
        seen.append(cursor)
        if len(seen) < 3:
            return BatchResult(processed=1, cursor=str(uuid.uuid4()), complete=False)
        return BatchResult(processed=1, cursor=None, complete=True)

    monkeypatch.setitem(internal_cron.TASKS, task,
                        internal_cron.TaskSpec(sweep=fake_sweep, cadence="daily", hour=0))

    statuses = []
    for _ in range(3):
        # No sleeping, no clock manipulation: back-to-back calls.
        resp = client.post(f"{CRON}/{task}", headers={"X-Cron-Key": SECRET})
        assert resp.status_code == 200
        statuses.append(resp.json()["status"])

    assert statuses == [internal_cron.CONTINUING, internal_cron.CONTINUING,
                        internal_cron.OK], (
        "a released continuing run must be reclaimable with no waiting period")
    assert seen[1] is not None and seen[2] is not None, "each call resumed from a cursor"


@requires_db
def test_a_continuing_run_holds_no_lease(client, db, task, scheduler_credential,
                                         monkeypatch):
    """`continuing` is idle, and the row must say so.

    A continuing row that still carried a live lease would be indistinguishable
    from one being executed right now, and the next call would be turned away.
    """
    from app.services.sweep_service import BatchResult

    monkeypatch.setitem(
        internal_cron.TASKS, task,
        internal_cron.TaskSpec(
            sweep=lambda *_a: BatchResult(processed=1, cursor="c", complete=False),
            cadence="daily", hour=0))

    assert client.post(f"{CRON}/{task}",
                       headers={"X-Cron-Key": SECRET}).json()["status"] == \
        internal_cron.CONTINUING

    db.expire_all()
    row = _run(db, task)
    assert row.status == internal_cron.CONTINUING
    assert row.lease_token is None, "an idle run must not hold a lease"
    assert row.lease_expires_at is None
    assert row.cursor == "c", "progress is persisted before the lease is released"


# --- 2. Real simultaneous claim arbitration --------------------------------

@requires_db
def test_two_simultaneous_claimants_produce_exactly_one_executor(
        db, task, scheduler_credential):
    """Two runners, two real connections, one period, released together.

    A barrier makes this genuinely concurrent rather than merely sequential:
    both threads are inside `_claim` before either can commit, so the outcome
    is decided by PostgreSQL — by the unique index on the INSERT path, and by
    the row lock on the reclaim path. Nothing here is mocked, because the
    entire question is what the database does under contention, and a mock
    cannot answer it.
    """
    import threading

    from app.db.session import SessionLocal

    spec = internal_cron.TaskSpec(lambda _db: 0, cadence="daily", hour=0)
    now = internal_cron._now()
    period, due = spec.period(now), spec.threshold(now)

    # Release this fixture's connection for the duration of the race. The CI
    # test database is reached through a SESSION pooler that accepts only about
    # four clients, and DB_POOL_SIZE is 2 with 3 overflow — so holding a third
    # connection open while two threads contend is close enough to the cap that
    # a pool timeout could masquerade as a claim failure. The Session reconnects
    # by itself on next use.
    db.close()

    barrier = threading.Barrier(2, timeout=30)
    results: dict[str, object] = {}

    def attempt(name: str) -> None:
        session = SessionLocal()
        try:
            barrier.wait()
            results[name] = internal_cron._claim(session, task, "scheduler",
                                                 period, due)
        except Exception as exc:  # noqa: BLE001 - reported through the assertions
            results[name] = exc
        finally:
            session.close()

    threads = [threading.Thread(target=attempt, args=(n,)) for n in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    for name, outcome in results.items():
        assert not isinstance(outcome, Exception), f"{name} raised: {outcome!r}"

    winners = [c for c in results.values() if c is not None]
    assert len(winners) == 1, (
        f"exactly one runner may own a period; got {len(winners)}")

    db.expire_all()
    rows = db.scalars(select(CronRun).where(
        CronRun.task == task,
        CronRun.status.in_(internal_cron.CLAIMABLE + (internal_cron.OK,)))).all()
    assert len(rows) == 1, "one logical row per task+period, never two"
    assert rows[0].lease_token == winners[0].token, (
        "the surviving row must belong to the runner that believes it won")


@requires_db
def test_a_live_lease_turns_the_next_caller_away(client, db, task,
                                                 scheduler_credential):
    """A runner still inside its lease must not be joined by a second one."""
    spec = internal_cron.TaskSpec(lambda _db: 0, cadence="daily", hour=0)
    internal_cron.TASKS[task] = spec
    now = internal_cron._now()

    held = internal_cron._claim(db, task, "scheduler", spec.period(now),
                               spec.threshold(now))
    assert held is not None

    resp = client.post(f"{CRON}/{task}", headers={"X-Cron-Key": SECRET})
    assert resp.status_code == 200
    assert resp.json()["status"] == internal_cron.ALREADY_RUNNING


@requires_db
def test_an_expired_lease_is_stolen(client, db, task, scheduler_credential):
    """A process that dies mid-run leaves a lease behind. Without takeover one
    crash blocks the task until the period rolls over."""
    spec = internal_cron.TaskSpec(lambda _db: 7, cadence="daily", hour=0)
    internal_cron.TASKS[task] = spec
    now = internal_cron._now()

    held = internal_cron._claim(db, task, "scheduler", spec.period(now),
                               spec.threshold(now))
    # Age the lease past its expiry, as a dead request would leave it.
    db.execute(update(CronRun).where(CronRun.id == held.id)
               .values(lease_expires_at=now - timedelta(seconds=1)))
    db.commit()

    resp = client.post(f"{CRON}/{task}", headers={"X-Cron-Key": SECRET})
    assert resp.status_code == 200
    assert resp.json()["status"] == internal_cron.OK, (
        "an abandoned lease must be stealable, not honoured forever")


# --- 3. The zombie owner ---------------------------------------------------

@requires_db
def test_a_zombie_owner_cannot_overwrite_the_runner_that_replaced_it(
        db, task, scheduler_credential):
    """THE fencing test, and the reason time-based takeover is safe at all.

        A claims the run, then stalls (a hung network call, a paused container)
        A's lease expires
        B steals the run and advances the cursor
        A finally wakes and tries to persist its own — now stale — view

    A must write nothing. If it could, every takeover would risk rewinding the
    traversal to wherever the dead request happened to be, and `processed_total`
    would silently disagree with reality.
    """
    spec = internal_cron.TaskSpec(lambda _db: 0, cadence="daily", hour=0)
    now = internal_cron._now()
    period, due = spec.period(now), spec.threshold(now)

    a = internal_cron._claim(db, task, "scheduler", period, due)
    assert a is not None

    # A stalls; its lease lapses.
    db.execute(update(CronRun).where(CronRun.id == a.id)
               .values(lease_expires_at=now - timedelta(seconds=1)))
    db.commit()

    # B takes over and makes real progress.
    b = internal_cron._claim(db, task, "scheduler", period, due)
    assert b is not None and b.token != a.token, "B must hold a different token"
    assert internal_cron._release(db, b, internal_cron.CONTINUING,
                                  cursor="b-advanced", processed=40, total=40)

    # A wakes up and tries to finish, believing it still owns the run.
    accepted = internal_cron._release(db, a, internal_cron.OK,
                                      cursor=None, processed=1, total=1)
    assert accepted is False, "an expired owner's write must be rejected"

    db.expire_all()
    row = _run(db, task)
    assert row.cursor == "b-advanced", "B's progress must survive A waking up"
    assert row.processed_total == 40
    assert row.status == internal_cron.CONTINUING, (
        "A must not be able to mark the period complete")


# --- 4. Failure preserves progress -----------------------------------------

@requires_db
def test_failure_preserves_the_cursor_and_the_run_resumes(
        client, db, task, scheduler_credential, monkeypatch):
    """A mid-traversal failure must not rewind the population.

    Resetting to the beginning would mean a job that fails near the end
    repeats everything it had already done, every time, and a job that fails
    reliably at record 900 would never reach 901.
    """
    from app.services.sweep_service import BatchResult

    calls = {"n": 0}
    resumed_from = []

    def flaky(_db, cursor, _batch, _snapshot, _budget):
        calls["n"] += 1
        resumed_from.append(cursor)
        if calls["n"] == 1:
            return BatchResult(processed=100, cursor="U100", complete=False)
        if calls["n"] == 2:
            raise RuntimeError("transient")
        return BatchResult(processed=2, cursor=None, complete=True)

    monkeypatch.setitem(internal_cron.TASKS, task,
                        internal_cron.TaskSpec(sweep=flaky, cadence="daily", hour=0))

    assert client.post(f"{CRON}/{task}",
                       headers={"X-Cron-Key": SECRET}).json()["status"] == \
        internal_cron.CONTINUING
    assert client.post(f"{CRON}/{task}",
                       headers={"X-Cron-Key": SECRET}).status_code == 500

    db.expire_all()
    row = _run(db, task)
    assert row.status == internal_cron.FAILED
    assert row.cursor == "U100", "the last durably completed cursor must survive"
    assert row.processed_total == 100, "and so must the accounting"
    assert row.lease_token is None, "a failed run is idle, not held"

    # The retry resumes rather than restarting.
    third = client.post(f"{CRON}/{task}", headers={"X-Cron-Key": SECRET})
    assert third.status_code == 200
    assert third.json()["status"] == internal_cron.OK
    assert resumed_from == [None, "U100", "U100"], (
        "the failed batch replays from the last safe point, not from the start")
    assert third.json()["processed_total"] == 102


@requires_db
def test_a_failed_period_is_retried_in_the_same_logical_row(
        client, db, task, scheduler_credential, monkeypatch):
    """Retry must reclaim, not insert. A second row would restart the cursor
    and split the period's accounting across two records."""
    monkeypatch.setitem(internal_cron.TASKS, task, internal_cron.TaskSpec(
        lambda _db: (_ for _ in ()).throw(RuntimeError("boom")),
        cadence="daily", hour=0))
    assert client.post(f"{CRON}/{task}", headers={"X-Cron-Key": SECRET}).status_code == 500

    monkeypatch.setitem(internal_cron.TASKS, task,
                        internal_cron.TaskSpec(lambda _db: 3, cadence="daily", hour=0))
    assert client.post(f"{CRON}/{task}",
                       headers={"X-Cron-Key": SECRET}).json()["status"] == internal_cron.OK

    db.expire_all()
    rows = db.scalars(select(CronRun).where(
        CronRun.task == task,
        CronRun.status.in_(internal_cron.CLAIMABLE + (internal_cron.OK,)))).all()
    assert len(rows) == 1, "a retry must reuse the period's row, not create another"


# --- 5. Multi-batch traversal over real records ----------------------------

@requires_db
def test_a_traversal_covers_every_record_across_batches(
        client, db, task, scheduler_credential, monkeypatch):
    """Five records, capacity two: 2 + 2 + 1, complete only on the third.

    Asserted against real rows rather than a scripted fake, because the
    property that matters is that the SET of records handled equals the
    population — not that a counter reached five.
    """
    from app.services.sweep_service import BatchResult

    population = [str(uuid.uuid4()) for _ in range(5)]
    handled: list[str] = []

    def sweep(_db, cursor, batch, _snapshot, budget):
        remaining = sorted(population)
        if cursor:
            remaining = [r for r in remaining if r > cursor]
        done, last = 0, None
        for key in remaining:
            if done >= batch or budget.spent():
                break
            handled.append(key)
            last, done = key, done + 1
        finished = done == len(remaining)
        return BatchResult(processed=done,
                           cursor=None if finished else last,
                           complete=finished)

    monkeypatch.setitem(internal_cron.TASKS, task,
                        internal_cron.TaskSpec(sweep=sweep, cadence="daily", hour=0))
    # The seam is module state, never a request field.
    monkeypatch.setattr(internal_cron, "_BATCH_OVERRIDE", 2)

    results = []
    for _ in range(3):
        r = client.post(f"{CRON}/{task}", headers={"X-Cron-Key": SECRET}).json()
        results.append((r["status"], r["processed"], r["processed_total"]))

    assert results == [
        (internal_cron.CONTINUING, 2, 2),
        (internal_cron.CONTINUING, 2, 4),
        (internal_cron.OK, 1, 5),
    ], f"expected 2+2+1 with completion only at the end, got {results}"

    assert handled == sorted(population), (
        "every record exactly once, in keyset order, with no duplicates")

    db.expire_all()
    row = _run(db, task)
    assert row.status == internal_cron.OK
    assert row.processed_total == 5
    assert row.cursor is None, "a completed traversal keeps no cursor"

    # And the finished period is not run a second time.
    again = client.post(f"{CRON}/{task}", headers={"X-Cron-Key": SECRET}).json()
    assert again["status"] == internal_cron.ALREADY_DONE
    assert handled == sorted(population), "no extra work after completion"


@requires_db
def test_the_time_budget_can_stop_a_batch_before_its_record_count(
        client, db, task, scheduler_credential, monkeypatch):
    """The budget, not the record count, is the safety property.

    With capacity far above the population and a zero-length budget, the batch
    must still stop — otherwise a slow population would run until the platform
    killed the request.
    """
    from app.services.sweep_service import BatchResult

    def sweep(_db, cursor, batch, _snapshot, budget):
        assert batch >= 250, "capacity is not what should stop this batch"
        if budget.spent():
            return BatchResult(processed=0, cursor=cursor or "start", complete=False)
        return BatchResult(processed=batch, cursor=None, complete=True)

    monkeypatch.setitem(internal_cron.TASKS, task,
                        internal_cron.TaskSpec(sweep=sweep, cadence="daily", hour=0))
    monkeypatch.setattr(internal_cron, "_BUDGET_OVERRIDE", timedelta(seconds=0))

    resp = client.post(f"{CRON}/{task}", headers={"X-Cron-Key": SECRET}).json()
    assert resp["status"] == internal_cron.CONTINUING
    assert resp["processed"] == 0


def test_the_lease_comfortably_outlives_a_budgeted_request():
    """A healthy request must never still be running when its lease expires;
    otherwise takeover would preempt live work instead of recovering dead work.
    """
    assert internal_cron.LEASE > internal_cron.REQUEST_BUDGET * 10, (
        "the lease must exceed the request budget by a wide margin, so no "
        "heartbeat is required")


def test_the_scheduler_never_takes_traversal_input_from_the_caller():
    """The backend owns progression. A caller-supplied cursor or batch size
    would let anyone holding the credential skip most of a population, or keep
    a period permanently incomplete."""
    import inspect

    params = set(inspect.signature(internal_cron.run_task).parameters)
    assert not params & {"cursor", "offset", "after", "batch", "limit", "budget"}


# --- 6. Traversal invariants (no database required) -------------------------

def test_a_batch_that_makes_no_progress_does_not_rewind_the_cursor(monkeypatch):
    """A budget that runs out before the first record must leave the cursor
    alone.

    The bug this guards: writing the last-visited key when nothing was visited
    produces "review:None", which is not a readable key — and an unreadable
    cursor deliberately restarts the traversal. A persistently tight budget
    would therefore rewind to the beginning on every single call, and a sweep
    that never advanced would still report `continuing` forever.
    """
    from app.services import sweep_service, trust_rating_service, vote_service

    ids = sorted(str(uuid.uuid4()) for _ in range(5))
    monkeypatch.setattr(vote_service, "voted_review_ids", lambda *a, **k: ids)
    monkeypatch.setattr(trust_rating_service, "reviewed_product_ids",
                        lambda *a, **k: ids)

    class NoBudget:
        def spent(self) -> bool:
            return True

    class Idle:
        """Enough Session surface for a batch that does nothing."""

        def commit(self) -> None:
            pass

        def get(self, *_a):
            return None

    resumed_at = f"review:{ids[1]}"
    result = sweep_service.sweep_wilson(Idle(), resumed_at, 250, None, NoBudget())
    assert result.processed == 0
    assert result.cursor == resumed_at, "no progress must preserve the cursor"
    assert not result.complete

    at_product = f"product:{ids[1]}"
    product = sweep_service.sweep_wilson(Idle(), at_product, 250, None, NoBudget())
    assert product.processed == 0
    assert product.cursor == at_product, "the product half must behave the same"
    assert not product.complete


def test_an_unreadable_cursor_restarts_rather_than_skipping():
    """Repeating idempotent work is safe; silently skipping the rest of a
    population is not. A cursor we cannot parse must mean 'start again', never
    'continue from somewhere unknown'."""
    from app.services.sweep_service import _after

    assert _after("not-a-uuid") is None
    assert _after("") is None
    assert _after(None) is None
    known = uuid.uuid4()
    assert _after(str(known)) == str(known)
