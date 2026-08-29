"""The production scheduler's entry point.

This route is the only thing standing between an unauthenticated caller and
eight maintenance jobs that mutate production data, so most of what follows is
about refusing people rather than about running tasks.

The tasks themselves keep their own coverage elsewhere; here the questions are:
who may invoke them, what may be invoked, what happens when two invocations
overlap, and whether anything sensitive leaks into a response or a run record.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.api.v1.routes import internal_cron
from tests.conftest import register_and_token, requires_db

CRON = "/api/v1/internal/cron"
SECRET = "test-scheduler-secret-not-used-anywhere-else"


@pytest.fixture
def scheduler_credential(db):
    """A live credential row, rolled back with the fixture."""
    from app.models.maintenance import CronCredential

    row = CronCredential(
        name=internal_cron.CREDENTIAL_NAME,
        secret_sha256=hashlib.sha256(SECRET.encode()).hexdigest(),
        is_active=True,
    )
    db.add(row)
    db.commit()          # the API opens its own session and must see it
    yield row
    db.delete(row)
    db.commit()


# --- Who may invoke -------------------------------------------------------

@requires_db
def test_no_credential_header_is_refused(client):
    resp = client.post(f"{CRON}/expire_requests")
    assert resp.status_code == 401


@requires_db
def test_a_wrong_secret_is_refused(client, scheduler_credential):
    resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": "not-the-secret"})
    assert resp.status_code == 401


@requires_db
def test_a_moderator_session_is_not_a_scheduler_credential(client, scheduler_credential):
    """Role and scheduler identity are different things. A moderator token must
    not open the maintenance endpoint just because it opens /admin."""
    _, token, _ = register_and_token(client, role="moderator")
    resp = client.post(f"{CRON}/expire_requests",
                       headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@requires_db
def test_the_correct_secret_is_accepted(client, scheduler_credential):
    resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    assert resp.status_code == 200, resp.text
    assert resp.json()["task"] == "expire_requests"


@requires_db
def test_an_inactive_credential_is_refused(client, db, scheduler_credential):
    scheduler_credential.is_active = False
    db.commit()
    resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    # No active credential at all -> fail closed, not open.
    assert resp.status_code in (401, 503)


# --- What may be invoked --------------------------------------------------

@requires_db
def test_an_unknown_task_is_refused(client, scheduler_credential):
    resp = client.post(f"{CRON}/drop_everything", headers={"X-Cron-Key": SECRET})
    assert resp.status_code == 404


@requires_db
def test_the_unknown_task_name_is_not_echoed_back(client, scheduler_credential):
    """The path is matched against an allow-list, not resolved to anything, and
    the response must not reflect attacker-supplied text."""
    probe = "zzz_probe_marker_zzz"
    resp = client.post(f"{CRON}/{probe}", headers={"X-Cron-Key": SECRET})
    assert probe not in resp.text


def test_every_allow_listed_task_is_callable():
    """A name in the list with no working callable behind it would fail only at
    3am in production."""
    for name, spec in internal_cron.TASKS.items():
        assert callable(spec.run), f"{name} has no runnable body"


def test_the_allow_list_covers_every_beat_task():
    """The scheduler replaced Celery beat; it must not silently drop a job."""
    import app.workers.tasks  # noqa: F401
    from app.workers.celery_app import celery_app

    beat = {e["task"].rsplit(".", 1)[-1] for e in celery_app.conf.beat_schedule.values()}
    scheduled = set(internal_cron.TASKS)
    # Two names differ deliberately; map them before comparing.
    aliases = {"run_pii_retention": "pii_retention",
               "run_honesty_fund_distribution": "honesty_fund_distribution"}
    beat = {aliases.get(name, name) for name in beat}
    assert beat <= scheduled, f"beat tasks with no scheduler entry: {beat - scheduled}"


# --- Cadence and catch-up ------------------------------------------------
#
# GitHub Actions does not guarantee delivery. These are the tests that stop a
# missed invocation from silently postponing a monthly job by a month.

def test_every_task_declares_a_real_cadence():
    for name, spec in internal_cron.TASKS.items():
        assert spec.cadence in ("daily", "monthly"), name
        if spec.cadence == "monthly":
            assert spec.day_of_month, f"{name} is monthly with no day"


def test_periods_are_dated_in_manila_not_utc():
    """18:30 UTC on the 4th is 02:30 Manila on the 5th. Reading the UTC date
    would file the run under the wrong month at a boundary."""
    from app.core.constants import MANILA

    spec = internal_cron.TASKS["schedule_payouts"]
    utc_moment = datetime(2026, 9, 4, 18, 30, tzinfo=UTC)
    assert utc_moment.astimezone(MANILA).day == 5
    assert spec.period(utc_moment) == "2026-09"
    assert spec.is_due(utc_moment) is True


def test_a_daily_period_is_a_date_and_a_monthly_period_is_a_month():
    from app.core.constants import MANILA

    when = datetime(2026, 8, 29, 12, 0, tzinfo=MANILA)
    assert internal_cron.TASKS["expire_requests"].period(when) == "2026-08-29"
    assert internal_cron.TASKS["honesty_fund_distribution"].period(when) == "2026-08"


def test_a_task_is_not_due_before_its_threshold():
    from app.core.constants import MANILA

    spec = internal_cron.TASKS["pii_retention"]          # 03:00 Manila
    assert spec.is_due(datetime(2026, 8, 29, 2, 59, tzinfo=MANILA)) is False
    assert spec.is_due(datetime(2026, 8, 29, 3, 0, tzinfo=MANILA)) is True


def test_a_missed_monthly_run_is_caught_up_later_in_the_same_period():
    """THE point of this design. If the scheduler never fired on the 1st, an
    invocation on the 2nd — or the 20th — must still be due, because the period
    is the month and the month has not been done."""
    from app.core.constants import MANILA

    spec = internal_cron.TASKS["honesty_fund_distribution"]
    missed_day = datetime(2026, 8, 2, 2, 0, tzinfo=MANILA)
    assert spec.is_due(missed_day) is True
    assert spec.period(missed_day) == "2026-08", "still August's run, not September's"

    much_later = datetime(2026, 8, 20, 9, 0, tzinfo=MANILA)
    assert spec.is_due(much_later) is True
    assert spec.period(much_later) == "2026-08"


def test_the_next_month_is_a_different_period():
    """Catch-up must not mean "run August again in September"."""
    from app.core.constants import MANILA

    spec = internal_cron.TASKS["honesty_fund_distribution"]
    assert spec.period(datetime(2026, 8, 20, 9, 0, tzinfo=MANILA)) == "2026-08"
    assert spec.period(datetime(2026, 9, 1, 9, 0, tzinfo=MANILA)) == "2026-09"


@requires_db
def test_a_completed_period_is_not_run_again(client, db, scheduler_credential):
    """Every extra invocation inside a period must be a no-op. This is what
    makes triggering a monthly job daily safe."""
    from app.core.constants import MANILA
    from app.models.maintenance import CronRun

    spec = internal_cron.TASKS["expire_requests"]
    period = spec.period(datetime.now(MANILA))

    first = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    assert first.status_code == 200
    assert first.json()["status"] == internal_cron.OK

    second = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    assert second.status_code == 200
    assert second.json()["status"] == internal_cron.ALREADY_DONE

    db.expire_all()
    successes = db.query(CronRun).filter(
        CronRun.task == "expire_requests", CronRun.period == period,
        CronRun.status == internal_cron.OK).count()
    assert successes == 1, "a period may succeed exactly once"


@requires_db
def test_a_failed_period_may_be_retried(client, db, monkeypatch, scheduler_credential):
    """A failure must not consume the period. If it did, one bad night would
    mean the job never ran that month."""
    from app.core.constants import MANILA

    spec = internal_cron.TASKS["expire_requests"]
    period = spec.period(datetime.now(MANILA))

    def boom(_db):
        raise RuntimeError("transient")

    monkeypatch.setitem(internal_cron.TASKS, "expire_requests",
                        internal_cron.TaskSpec(boom, cadence="daily", hour=0))
    failed = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    assert failed.status_code == 500

    monkeypatch.undo()
    retried = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    assert retried.status_code == 200
    assert retried.json()["status"] == internal_cron.OK, "a failed period must retry"
    assert retried.json()["period"] == period


@requires_db
def test_a_task_before_its_threshold_records_not_due(client, monkeypatch,
                                                     scheduler_credential):
    """An early scheduler must be told it is early, distinctly from being told
    the work is already done."""
    late = internal_cron.TaskSpec(lambda _db: 0, cadence="daily", hour=23, minute=59)
    monkeypatch.setitem(internal_cron.TASKS, "expire_requests", late)

    resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    assert resp.status_code == 200
    assert resp.json()["status"] == internal_cron.NOT_DUE


def test_the_skip_reasons_are_distinct():
    """Collapsing these into one "skipped" would hide a scheduler that had
    stopped working behind one that was merely early."""
    reasons = {internal_cron.NOT_DUE, internal_cron.ALREADY_DONE,
               internal_cron.ALREADY_RUNNING}
    assert len(reasons) == 3
    assert internal_cron.OK not in reasons and internal_cron.FAILED not in reasons


# --- Overlap and repetition ------------------------------------------------

@requires_db
def test_a_second_invocation_while_one_holds_the_lock_is_reported(client, db, scheduler_credential):
    """Schedulers retry. Two runners inside one sweep would double the work, so
    the second must be told it is already running rather than proceeding."""
    from sqlalchemy import text

    key = internal_cron._lock_key("expire_requests")
    # Hold the lock on a separate session, as a concurrent runner would.
    db.execute(text("SELECT pg_advisory_lock(:ns, :key)"),
               {"ns": internal_cron._LOCK_NAMESPACE, "key": key})
    db.commit()
    try:
        resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
        assert resp.status_code == 200
        assert resp.json()["status"] == internal_cron.ALREADY_RUNNING
    finally:
        db.execute(text("SELECT pg_advisory_unlock(:ns, :key)"),
                   {"ns": internal_cron._LOCK_NAMESPACE, "key": key})
        db.commit()


@requires_db
def test_running_the_same_task_twice_is_safe(client, scheduler_credential):
    """Neither call errors; the second reports the period already done."""
    seen = []
    for _ in range(2):
        resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
        assert resp.status_code == 200
        seen.append(resp.json()["status"])
    assert seen[0] in (internal_cron.OK, internal_cron.ALREADY_DONE)
    assert seen[1] == internal_cron.ALREADY_DONE


# --- What is recorded ------------------------------------------------------

@requires_db
def test_every_invocation_is_recorded(client, db, scheduler_credential):
    from app.models.maintenance import CronRun

    before = db.query(CronRun).filter(CronRun.task == "expire_requests").count()
    client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    db.expire_all()
    after = db.query(CronRun).filter(CronRun.task == "expire_requests").count()
    assert after == before + 1


@requires_db
def test_the_response_carries_no_secret_material(client, scheduler_credential):
    resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    body = resp.text
    assert SECRET not in body
    assert hashlib.sha256(SECRET.encode()).hexdigest() not in body


@requires_db
def test_a_failing_task_records_a_class_not_a_message(client, db, monkeypatch,
                                                      scheduler_credential):
    """A run record is readable by moderators, so a failure must not carry row
    data in a message — the same rule the admin Overview's diagnostics follow."""
    from app.models.maintenance import CronRun

    def boom(_db):
        raise ValueError("secret-row-value-42")

    monkeypatch.setitem(internal_cron.TASKS, "expire_requests",
                        internal_cron.TaskSpec(boom, cadence="daily", hour=0))

    resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    assert resp.status_code == 500
    assert "secret-row-value-42" not in resp.text

    db.expire_all()
    run = (db.query(CronRun).filter(CronRun.task == "expire_requests")
           .order_by(CronRun.started_at.desc()).first())
    assert run is not None
    assert run.status == "failed"
    assert run.failure == "ValueError"
    assert "secret-row-value-42" not in (run.detail or "")


# --- The jobs still do their job -------------------------------------------

@requires_db
def test_request_expiry_transitions_only_what_is_due(client, db, scheduler_credential):
    """Before expires_at: untouched. After: expired. Both proved on run-owned
    rows, so the shared project's contents cannot make this pass or fail."""
    from app.models.enums import RequestStatus
    from app.models.request_board import ReviewRequest
    from tests.conftest import make_user

    owner = make_user(db, display_name="Expiry probe")
    db.flush()
    now = datetime.now(UTC)
    due = ReviewRequest(requester_id=owner.id, title="Due request",
                        details="x" * 40, status=RequestStatus.open,
                        expires_at=now - timedelta(hours=1))
    fresh = ReviewRequest(requester_id=owner.id, title="Fresh request",
                          details="x" * 40, status=RequestStatus.open,
                          expires_at=now + timedelta(days=7))
    db.add_all([due, fresh])
    db.commit()
    try:
        resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
        assert resp.status_code == 200

        db.expire_all()
        db.refresh(due)
        db.refresh(fresh)
        assert due.status == RequestStatus.expired, "a request past its term must expire"
        assert fresh.status == RequestStatus.open, "a request still in term must not"
    finally:
        for row in (due, fresh):
            db.delete(row)
        db.commit()


@requires_db
def test_pii_retention_runs_and_reports_a_count(client, scheduler_credential):
    """The legal obligation that most needed automating. It uses the retention
    policy already configured; nothing here invents a duration."""
    resp = client.post(f"{CRON}/pii_retention", headers={"X-Cron-Key": SECRET})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["processed"], int)


@requires_db
def test_payout_scheduling_prepares_without_submitting(client, scheduler_credential,
                                                       monkeypatch):
    """Automating internal preparation must not become an automatic transfer.
    If the scheduler ever reached the provider, this fails."""
    from app.services import payout_service

    submitted = []
    monkeypatch.setattr(payout_service, "submit_batch",
                        lambda *a, **k: submitted.append(a) or {})

    resp = client.post(f"{CRON}/schedule_payouts", headers={"X-Cron-Key": SECRET})
    assert resp.status_code == 200
    assert submitted == [], "the scheduler must not hand a batch to the provider"


@requires_db
def test_the_scheduler_does_not_expose_arbitrary_execution(client, scheduler_credential):
    """Path traversal and dotted attribute paths must not resolve to anything."""
    for probe in ("../../admin/payouts/run", "os.system", "app.workers.tasks.schedule_payouts"):
        resp = client.post(f"{CRON}/{probe}", headers={"X-Cron-Key": SECRET})
        assert resp.status_code in (404, 405), f"{probe} resolved to something"


def test_lock_keys_are_distinct_per_task():
    """One shared lock id would make unrelated jobs block each other."""
    keys = {name: internal_cron._lock_key(name) for name in internal_cron.TASKS}
    assert len(set(keys.values())) == len(keys), f"colliding lock keys: {keys}"


def test_the_credential_is_never_stored_in_plaintext():
    """The model holds a digest column and no secret column."""
    from app.models.maintenance import CronCredential

    columns = set(CronCredential.__table__.columns.keys())
    assert "secret_sha256" in columns
    assert not {"secret", "token", "password", "plaintext"} & columns


@requires_db
def test_uuid_columns_serialize_as_strings(client, scheduler_credential):
    """The admin Overview went down for exactly this: a UUID reaching a str
    field. The run id crosses the same boundary."""
    resp = client.post(f"{CRON}/expire_requests", headers={"X-Cron-Key": SECRET})
    run_id = resp.json().get("run_id")
    if run_id:
        assert isinstance(run_id, str)
        uuid.UUID(run_id)
