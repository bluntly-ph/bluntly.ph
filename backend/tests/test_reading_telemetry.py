"""Reading telemetry: model shape and privacy boundaries.

The constraint tests for this subsystem run against PostgreSQL in the later
collection task.  These fast model tests establish its public schema contract.
"""

from __future__ import annotations

import importlib.util
import io
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.models.enums import ReaderKind
from app.models.telemetry import ReviewReadingSession
from app.models.traffic import ReviewFirstVoteGeoBucket
from app.services import reading_telemetry_service as svc


def test_reader_kind_has_exactly_two_members():
    assert {member.value for member in ReaderKind} == {"anon", "user"}


def test_the_model_declares_the_columns_the_service_writes():
    columns = set(ReviewReadingSession.__table__.columns.keys())
    assert {
        "impression_id",
        "review_id",
        "reader_kind",
        "reader_ref",
        "anon_ref",
        "started_at",
        "last_seen_at",
        "active_ms",
        "body_active_ms",
        "wall_ms",
        "scroll_milestone",
        "checkpoints",
        "max_seq",
        "clamped",
        "vote_client_after_ms",
        "report_client_after_ms",
        "comment_client_after_ms",
        "share_client_after_ms",
        "photo_client_after_ms",
        "outlink_client_after_ms",
        "first_vote_at",
        "active_ms_at_first_vote",
        "country",
        "word_count_at_view",
        "star_rating_at_view",
        "device_class",
    } <= columns


def test_no_user_agent_column_exists():
    """The raw User-Agent is never persisted — only the derived bucket."""
    columns = set(ReviewReadingSession.__table__.columns.keys())
    assert "user_agent" not in columns
    assert "device_class" in columns


def test_checkpoints_default_satisfies_its_database_constraint():
    default = ReviewReadingSession.__table__.c.checkpoints.server_default
    assert default is not None
    assert default.arg == "1"


def test_model_metadata_declares_the_migration_indexes():
    reading_indexes = {index.name: index for index in ReviewReadingSession.__table__.indexes}
    assert set(reading_indexes) == {
        "uq_reading_impression",
        "ix_reading_started_at",
        "ix_reading_review_started",
        "ix_reading_reader_review",
    }
    assert reading_indexes["uq_reading_impression"].unique
    assert (
        str(reading_indexes["ix_reading_reader_review"].dialect_options["postgresql"]["where"])
        == "reader_ref IS NOT NULL"
    )

    geo_indexes = {index.name: index for index in ReviewFirstVoteGeoBucket.__table__.indexes}
    assert set(geo_indexes) == {
        "uq_review_first_vote_geo",
        "ix_review_first_vote_geo_start",
    }
    geo_unique_index = geo_indexes["uq_review_first_vote_geo"]
    assert geo_unique_index.unique
    assert geo_unique_index.dialect_options["postgresql"]["nulls_not_distinct"]


def test_migration_emits_reader_kind_type_once():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "0041_reading_telemetry.py"
    spec = importlib.util.spec_from_file_location("reading_telemetry_migration", path)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    migration.op = Operations(context)
    migration.upgrade()

    assert output.getvalue().count("CREATE TYPE reader_kind") == 1


def _cp(**over):
    base = dict(
        impression_id=uuid.uuid4(),
        review_id=uuid.uuid4(),
        seq=1,
        active_ms=1000,
        body_active_ms=800,
        wall_ms=2000,
        scroll_pct=50,
        vote_after_ms=None,
        report_after_ms=None,
        comment_after_ms=None,
        share_after_ms=None,
        photo_after_ms=None,
        outlink_after_ms=None,
    )
    base.update(over)
    return svc.CheckpointData(**base)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 0),
        (1, 0),
        (24, 0),
        (25, 25),
        (49, 25),
        (50, 50),
        (74, 50),
        (75, 75),
        (99, 75),
        (100, 100),
        (-5, 0),
        (999, 100),
    ],
)
def test_scroll_snaps_to_the_five_legal_values(raw, expected):
    assert svc.snap_scroll(raw) == expected


@pytest.mark.parametrize(
    ("ua", "expected"),
    [
        (None, 0),
        ("", 0),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1", 1),
        ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile Safari", 1),
        ("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1 Mobile", 2),
        ("Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 Safari", 2),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome Safari", 3),
        ("curl/8.4.0", 0),
    ],
)
def test_device_class_is_derived_from_the_user_agent(ua, expected):
    assert svc.device_class_from_user_agent(ua) == expected


def test_device_class_is_always_in_range():
    for ua in (None, "", "x" * 5000, "\x00\x01", "Android Mobile iPad"):
        assert 0 <= svc.device_class_from_user_agent(ua) <= 3


def test_active_ms_is_capped_at_the_session_maximum():
    out = svc.clamp(_cp(active_ms=9_000_000, body_active_ms=0, wall_ms=0))
    assert out.active_ms == svc.MAX_SESSION_MS
    assert out.clamped is True


def test_body_active_never_exceeds_active():
    out = svc.clamp(_cp(active_ms=1000, body_active_ms=5000))
    assert out.body_active_ms == 1000
    assert out.clamped is True


def test_wall_ms_is_capped():
    out = svc.clamp(_cp(wall_ms=9_000_000))
    assert out.wall_ms == svc.MAX_SESSION_MS
    assert out.clamped is True


def test_elapsed_time_bounds_the_claimed_active_time():
    out = svc.clamp(_cp(active_ms=600_000, body_active_ms=0), elapsed_ms=3_000)
    assert out.active_ms == 3_000 + svc.SKEW_TOLERANCE_MS
    assert out.clamped is True


def test_an_honest_checkpoint_is_not_flagged():
    out = svc.clamp(
        _cp(active_ms=41_210, body_active_ms=38_900, wall_ms=61_004, scroll_pct=75),
        elapsed_ms=62_000,
    )
    assert (out.active_ms, out.body_active_ms, out.wall_ms) == (41_210, 38_900, 61_004)
    assert out.scroll_milestone == 75
    assert out.clamped is False


def test_clamp_output_satisfies_every_check_constraint():
    for active, body, wall, scroll in [
        (-5, -5, -5, -5),
        (10**9, 10**9, 10**9, 10**9),
        (0, 99, 0, 33),
        (1_800_000, 1_800_000, 1_800_000, 100),
    ]:
        out = svc.clamp(
            _cp(active_ms=active, body_active_ms=body, wall_ms=wall, scroll_pct=scroll)
        )
        assert 0 <= out.active_ms <= svc.MAX_SESSION_MS
        assert 0 <= out.body_active_ms <= out.active_ms
        assert 0 <= out.wall_ms <= svc.MAX_SESSION_MS
        assert out.scroll_milestone in svc.SCROLL_MILESTONES
