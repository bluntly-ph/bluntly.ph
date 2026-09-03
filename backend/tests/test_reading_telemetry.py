"""Reading telemetry: model shape and privacy boundaries.

The constraint tests for this subsystem run against PostgreSQL in the later
collection task.  These fast model tests establish its public schema contract.
"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.models.enums import ReaderKind
from app.models.telemetry import ReviewReadingSession
from app.models.traffic import ReviewFirstVoteGeoBucket


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
