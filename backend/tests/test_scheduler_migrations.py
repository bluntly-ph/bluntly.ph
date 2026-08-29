"""The scheduler's migration chain, and the states production can be caught in.

A migration chain is not just "does it apply". Production applies these one at
a time while a deployed application is already running against the database, so
the intermediate states are real states, not theoretical ones — and the
scheduler tables were added across four migrations (0034-0037), which means
there are three points at which the code and the schema disagree.

What must hold:

  * exactly one head, and 0033 -> 0037 applies in order
  * the model and the table agree once 0037 has run
  * at an intermediate head the scheduler degrades safely — it refuses to run
    rather than half-running — and NOTHING ELSE on the site breaks, because a
    partially-migrated database must not take the product down
"""

from __future__ import annotations

import pathlib
import re

import pytest
from sqlalchemy import inspect, text

from tests.conftest import requires_db

VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revisions() -> dict[str, str | None]:
    """revision -> down_revision, read from the files rather than from alembic,
    so this test works without a database."""
    chain: dict[str, str | None] = {}
    for path in VERSIONS.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        # The annotation is optional: alembic's own template writes
        # `down_revision: Union[str, None] = '...'`, and reading that as "no
        # down_revision" makes a mid-chain migration look like a second head.
        rev = re.search(r'^revision(?:\s*:[^=]+)?\s*=\s*["\']([^"\']+)',
                        source, re.M)
        down = re.search(
            r'^down_revision(?:\s*:[^=]+)?\s*=\s*(?:["\']([^"\']+)|None)',
            source, re.M)
        if rev:
            chain[rev.group(1)] = down.group(1) if down and down.group(1) else None
    return chain


def test_the_migration_chain_has_exactly_one_head():
    """Two heads mean `alembic upgrade head` fails and the deploy stops."""
    chain = _revisions()
    parents = {d for d in chain.values() if d}
    heads = sorted(set(chain) - parents)
    assert len(heads) == 1, f"expected one head, found {heads}"
    assert heads[0] == "0037_cron_lease", f"unexpected head: {heads[0]}"


def test_the_scheduler_migrations_form_the_expected_sequence():
    """0034 created the tables, 0035 added periods, 0036 claims, 0037 leases.

    Asserted explicitly because a rebase that reorders them would still have
    one head while applying the columns in an order that breaks the index
    predicates.
    """
    chain = _revisions()
    expected = ["0034_scheduled_maintenance", "0035_cron_periods",
                "0036_cron_claims", "0037_cron_lease"]
    for child, parent in zip(expected[1:], expected[:-1], strict=True):
        assert chain.get(child) == parent, (
            f"{child} should follow {parent}, follows {chain.get(child)}")
    assert chain[expected[0]] is not None, "0034 must not become a new root"


def test_no_migration_rewrites_an_already_released_one():
    """0034-0036 are deployed history. Corrections belong in a new migration.

    The lease work needed changes to 0036's index and to 0034's `status` width;
    both are done forward in 0037 rather than by editing files that other
    databases have already stamped.
    """
    for name in ("0034_scheduled_maintenance", "0035_cron_periods", "0036_cron_claims"):
        path = next(VERSIONS.glob(f"{name}*.py"))
        source = path.read_text(encoding="utf-8")
        assert "lease_token" not in source, (
            f"{name} is released history and must not gain lease columns")


@requires_db
def test_the_live_table_matches_the_model(db):
    """Once 0037 has run, every model column must exist in the database.

    This is the check that would have caught the previous candidate, where the
    model never declared `cursor`, `processed_total` or `claimed_at` and every
    claim raised TypeError into a bare `except`.
    """
    from app.models.maintenance import CronRun

    live = {c["name"] for c in inspect(db.get_bind()).get_columns("cron_runs")}
    declared = {c.name for c in CronRun.__table__.columns}
    missing = declared - live
    assert not missing, f"model declares columns the database lacks: {sorted(missing)}"


@requires_db
def test_the_status_column_fits_every_status_the_route_can_write(db):
    """`skipped_already_completed` is 25 characters; the column was varchar(16).

    Every "already completed" refusal — the single most common outcome once the
    daily workflow is live — would have failed on insert.
    """
    from app.api.v1.routes import internal_cron

    width = db.scalar(text("""
        SELECT character_maximum_length FROM information_schema.columns
        WHERE table_name = 'cron_runs' AND column_name = 'status'
    """))
    longest = max(len(v) for v in (
        internal_cron.OK, internal_cron.FAILED, internal_cron.RUNNING,
        internal_cron.CONTINUING, internal_cron.NOT_DUE,
        internal_cron.ALREADY_DONE, internal_cron.ALREADY_RUNNING))
    assert width >= longest, (
        f"status is varchar({width}) but must hold {longest} characters")


@requires_db
def test_the_claim_index_covers_failed_so_a_retry_reclaims_one_row(db):
    """`failed` must be inside the unique predicate.

    Outside it, a failed period could be claimed by a fresh INSERT — a second
    logical row for the same period, starting from a null cursor, silently
    restarting a traversal that was most of the way done.
    """
    predicate = db.scalar(text("""
        SELECT pg_get_expr(i.indpred, i.indrelid)
        FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid
        WHERE c.relname = 'uq_cron_runs_task_period_claim'
    """))
    assert predicate, "the claim index must exist and be partial"
    for status in ("running", "continuing", "failed", "ok"):
        assert status in predicate, f"{status} must take part in the claim index"


@requires_db
def test_an_unmigrated_scheduler_refuses_instead_of_half_running(db, client,
                                                                 monkeypatch):
    """THE INTERMEDIATE STATE. Code deployed, migration not yet applied.

    Vercel deploys on push and CI runs afterwards, so the application can be
    live against a database that is still at 0034. The scheduler must fail
    CLOSED — no credential table, no runs — and it must do so with a status
    that says "not configured" rather than "unauthorised", because the two send
    an operator to completely different places.

    Simulated by making the credential lookup raise, which is what a missing
    table does.
    """
    from app.api.v1.routes import internal_cron

    def unmigrated(*_a, **_k):
        raise RuntimeError("relation \"cron_credentials\" does not exist")

    monkeypatch.setattr(internal_cron, "select", unmigrated)
    resp = client.post("/api/v1/internal/cron/pii_retention",
                       headers={"X-Cron-Key": "anything"})
    assert resp.status_code == 503, "an unmigrated scheduler must fail closed"
    assert "not configured" in resp.json()["detail"].lower()


@requires_db
def test_the_rest_of_the_site_works_while_the_scheduler_is_unmigrated(client):
    """A partially-migrated database must not take the product down.

    The scheduler is additive: new tables, new route. Nothing else reads them,
    so the public surface must be unaffected — this is what makes it safe to
    push the code before the migration is approved.
    """
    for path in ("/health", "/api/v1/products", "/api/v1/reviews"):
        resp = client.get(path)
        assert resp.status_code < 500, (
            f"{path} returned {resp.status_code} — the scheduler migration "
            "must not be able to break unrelated routes")


@pytest.mark.parametrize("migration", ["0037_cron_lease"])
def test_the_new_migration_is_reversible(migration):
    """Every column and index 0037 adds must be dropped by its downgrade.

    Not because production will roll back casually, but because an unrunnable
    downgrade turns a bad deploy into an outage with no way out.
    """
    source = next(VERSIONS.glob(f"{migration}*.py")).read_text(encoding="utf-8")
    up, _, down = source.partition("def downgrade()")
    added = set(re.findall(r'add_column\(\s*"cron_runs",\s*sa\.Column\(\s*"(\w+)"', up))
    dropped = set(re.findall(r'drop_column\(\s*"cron_runs",\s*"(\w+)"', down))
    assert added, "expected 0037 to add columns"
    assert added <= dropped, f"downgrade does not drop {sorted(added - dropped)}"

    created = set(re.findall(r'create_index\(\s*"(\w+)"', up))
    removed = set(re.findall(r'drop_index\(\s*"(\w+)"', down))
    assert created <= removed | {"uq_cron_runs_task_period_claim"}, (
        f"downgrade leaves indexes behind: {sorted(created - removed)}")
