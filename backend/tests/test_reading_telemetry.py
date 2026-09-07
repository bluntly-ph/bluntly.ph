"""Reading telemetry: model shape and privacy boundaries.

The constraint tests for this subsystem run against PostgreSQL in the later
collection task.  These fast model tests establish its public schema contract.
"""

from __future__ import annotations

import importlib.util
import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import delete, event, select, update
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.core.errors import RateLimitError
from app.core.security import create_access_token
from app.main import app
from app.models.enums import ReaderKind, Verdict
from app.models.product import Product
from app.models.review import Review
from app.models.telemetry import ReviewReadingSession
from app.models.traffic import ReviewFirstVoteGeoBucket
from app.models.user import User
from app.services import reading_telemetry_service as svc
from tests.conftest import requires_db

USER_ID = uuid.UUID("10000000-0000-4000-8000-000000000001")
OTHER_USER_ID = uuid.UUID("10000000-0000-4000-8000-000000000002")
PRODUCT_ID = uuid.UUID("20000000-0000-4000-8000-000000000001")
REVIEW_ID = uuid.UUID("30000000-0000-4000-8000-000000000001")
OTHER_REVIEW_ID = uuid.UUID("30000000-0000-4000-8000-000000000002")
IMPRESSION_ID = uuid.UUID("40000000-0000-4000-8000-000000000001")
ANON_ID = uuid.UUID("50000000-0000-4000-8000-000000000001")


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


def _http_payload(**overrides):
    payload = {
        "impression_id": "40000000-0000-4000-8000-000000000001",
        "review_id": "30000000-0000-4000-8000-000000000001",
        "seq": 0,
        "active_ms": 1000,
        "body_active_ms": 800,
        "wall_ms": 2000,
        "scroll_pct": 50,
        "vote_after_ms": None,
        "report_after_ms": None,
        "comment_after_ms": None,
        "share_after_ms": None,
        "photo_after_ms": None,
        "outlink_after_ms": None,
    }
    payload.update(overrides)
    return payload


def _reading_checkpoint_in(**overrides):
    from app.api.v1.routes.reading_telemetry import ReadingCheckpointIn

    return ReadingCheckpointIn(**_http_payload(**overrides))


@pytest.fixture
def telemetry_context(db):
    """Two real reviews and users, deleted by exact id even after service commits."""

    def clean() -> None:
        db.rollback()
        db.execute(delete(Product).where(Product.id == PRODUCT_ID))
        db.execute(delete(User).where(User.id.in_([USER_ID, OTHER_USER_ID])))
        db.commit()

    clean()
    user = User(
        id=USER_ID,
        email="telemetry-reader@example.com",
        username="telemetry_reader",
        display_name="Telemetry Reader",
    )
    other_user = User(
        id=OTHER_USER_ID,
        email="telemetry-other-reader@example.com",
        username="telemetry_other_reader",
        display_name="Other Telemetry Reader",
    )
    product = Product(id=PRODUCT_ID, canonical_name="Telemetry Fixture Product")
    # Flushed before either review is constructed. `Review.author_id`/
    # `product_id` are bare FK columns with no declared `relationship()`, so
    # SQLAlchemy's unit-of-work has no dependency edge forcing `users`/
    # `products` to insert before `reviews` — batching all five objects into
    # one `add_all`/`commit` lets it flush them in the wrong order and fail
    # with a FK violation on a genuinely empty table. Flushing the parents
    # first (the pattern `make_user` + `test_affiliate_ingest.py` already use
    # elsewhere in this suite) sidesteps the ordering question entirely.
    db.add_all([user, other_user, product])
    db.flush()
    review = Review(
        id=REVIEW_ID,
        product_id=PRODUCT_ID,
        author_id=USER_ID,
        title="Telemetry fixture review",
        discussion="Four literal words here.",
        verdict=Verdict.it_depends,
        star_rating=4,
    )
    other_review = Review(
        id=OTHER_REVIEW_ID,
        product_id=PRODUCT_ID,
        author_id=OTHER_USER_ID,
        title="Other telemetry fixture review",
        discussion="A different review body.",
        verdict=Verdict.hard_pass,
        star_rating=2,
    )
    db.add_all([review, other_review])
    db.commit()
    try:
        yield SimpleNamespace(
            user=user,
            other_user=other_user,
            review=review,
            other_review=other_review,
        )
    finally:
        clean()


def _service_checkpoint(**overrides):
    payload = {
        "impression_id": IMPRESSION_ID,
        "review_id": REVIEW_ID,
        "seq": 0,
        "active_ms": 100,
        "body_active_ms": 80,
        "wall_ms": 200,
        "scroll_pct": 25,
        "vote_after_ms": None,
        "report_after_ms": None,
        "comment_after_ms": None,
        "share_after_ms": None,
        "photo_after_ms": None,
        "outlink_after_ms": None,
    }
    payload.update(overrides)
    return svc.CheckpointData(**payload)


def _user_identity(user_id=USER_ID):
    return svc.ReaderIdentity(kind=ReaderKind.user, reader_ref=user_id)


def _anon_identity(anon_id=ANON_ID):
    return svc.ReaderIdentity(kind=ReaderKind.anon, anon_ref=anon_id)


def _stored_row(db, impression_id=IMPRESSION_ID):
    db.expire_all()
    return db.scalar(
        select(ReviewReadingSession).where(
            ReviewReadingSession.impression_id == impression_id
        )
    )


def _row_snapshot(row):
    columns = tuple(row.__table__.columns)
    return columns, tuple(getattr(row, column.name) for column in columns)


def test_checkpoint_forbids_unknown_identity_fields():
    from app.api.v1.routes.reading_telemetry import ReadingCheckpointIn

    forbidden = {
        "user_id": "10000000-0000-4000-8000-000000000001",
        "country": "PH",
        "occurred_at": "2026-09-03T00:00:00Z",
        "device_class": 3,
    }
    for field, value in forbidden.items():
        with pytest.raises(ValidationError):
            ReadingCheckpointIn(**_http_payload(**{field: value}))


@pytest.mark.parametrize(
    "field",
    [
        "seq",
        "active_ms",
        "body_active_ms",
        "wall_ms",
        "vote_after_ms",
        "report_after_ms",
        "comment_after_ms",
        "share_after_ms",
        "photo_after_ms",
        "outlink_after_ms",
    ],
)
@pytest.mark.parametrize(
    "invalid",
    [-1, 2_147_483_648, True, "1000", 1.5, float("nan"), float("inf"), [], {}],
)
def test_checkpoint_rejects_negative_or_non_finite_durations(field, invalid):
    with pytest.raises(ValidationError):
        _reading_checkpoint_in(**{field: invalid})


@pytest.mark.parametrize("invalid", [-1, 1, 24, 26, 99, 101, True, "50", 50.0])
def test_checkpoint_rejects_off_grid_or_coercive_scroll(invalid):
    with pytest.raises(ValidationError):
        _reading_checkpoint_in(scroll_pct=invalid)


def test_checkpoint_accepts_only_uuid4_impressions():
    from app.api.v1.routes.reading_telemetry import ReadingCheckpointIn

    version_one = _http_payload(impression_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    with pytest.raises(ValidationError):
        ReadingCheckpointIn.model_validate_json(json.dumps(version_one))

    version_four = _http_payload(impression_id="550e8400-e29b-41d4-a716-446655440000")
    parsed = ReadingCheckpointIn.model_validate_json(json.dumps(version_four))
    assert parsed.impression_id == uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


@requires_db
def test_first_checkpoint_creates_one_server_derived_user_row(db, telemetry_context):
    assert svc.record_checkpoint(
        db,
        _service_checkpoint(),
        _user_identity(telemetry_context.user.id),
        country=" ph ",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )

    row = _stored_row(db)
    assert row.reader_kind == ReaderKind.user
    assert row.reader_ref == telemetry_context.user.id
    assert row.anon_ref is None
    assert row.checkpoints == 1
    assert row.max_seq == 0
    assert row.country == "PH"
    assert row.word_count_at_view == 4
    assert row.star_rating_at_view == 4
    assert row.device_class == 3
    assert row.started_at is not None
    assert row.last_seen_at is not None


@requires_db
def test_first_checkpoint_commits_so_a_second_connection_can_see_it(db, telemetry_context):
    """`changed` now comes from the RETURNING scalar, not rowcount -- prove
    the row it reports is actually committed, not merely visible within
    record_checkpoint's own still-open transaction. A second, independent
    connection from the same pool can only see it if `db.commit()` really
    ran on real PostgreSQL."""
    assert svc.record_checkpoint(
        db,
        _service_checkpoint(),
        _user_identity(telemetry_context.user.id),
        country=None,
        user_agent=None,
    )

    engine = db.get_bind()
    with engine.connect() as other_connection:
        visible = other_connection.execute(
            select(ReviewReadingSession.id).where(
                ReviewReadingSession.impression_id == IMPRESSION_ID
            )
        ).scalar_one_or_none()
    assert visible is not None


@requires_db
def test_first_checkpoint_creates_one_anon_row_without_user_identity(db, telemetry_context):
    assert svc.record_checkpoint(
        db,
        _service_checkpoint(),
        _anon_identity(),
        country=None,
        user_agent=None,
    )

    row = _stored_row(db)
    assert row.reader_kind == ReaderKind.anon
    assert row.reader_ref is None
    assert row.anon_ref == ANON_ID
    assert row.checkpoints == 1
    assert row.max_seq == 0


@requires_db
def test_replay_and_older_sequence_are_noops(db, telemetry_context):
    checkpoint = _service_checkpoint(seq=2)
    assert svc.record_checkpoint(
        db, checkpoint, _user_identity(), country="PH", user_agent=None
    )
    row = _stored_row(db)
    columns, before = _row_snapshot(row)

    assert not svc.record_checkpoint(
        db, checkpoint, _user_identity(), country="US", user_agent="Mozilla/5.0"
    )
    replayed = _stored_row(db)
    assert tuple(getattr(replayed, column.name) for column in columns) == before

    assert not svc.record_checkpoint(
        db,
        _service_checkpoint(seq=1, active_ms=999, wall_ms=999, scroll_pct=100),
        _user_identity(),
        country="US",
        user_agent="Mozilla/5.0",
    )
    older = _stored_row(db)
    assert tuple(getattr(older, column.name) for column in columns) == before


@requires_db
def test_later_checkpoint_advances_only_monotonic_fields(db, telemetry_context):
    assert svc.record_checkpoint(
        db, _service_checkpoint(), _user_identity(), country=None, user_agent=None
    )
    assert svc.record_checkpoint(
        db,
        _service_checkpoint(
            seq=1,
            active_ms=150,
            body_active_ms=70,
            wall_ms=250,
            scroll_pct=0,
        ),
        _user_identity(),
        country="US",
        user_agent="Mozilla/5.0 (iPhone; Mobile)",
    )

    row = _stored_row(db)
    assert (row.active_ms, row.body_active_ms, row.wall_ms) == (150, 80, 250)
    assert row.scroll_milestone == 25
    assert row.checkpoints == 2
    assert row.max_seq == 1
    assert row.country is None
    assert row.device_class == 0


@requires_db
def test_cross_reader_and_cross_review_replays_change_nothing(db, telemetry_context):
    assert svc.record_checkpoint(
        db, _service_checkpoint(), _user_identity(), country="PH", user_agent=None
    )
    row = _stored_row(db)
    columns, before = _row_snapshot(row)

    assert not svc.record_checkpoint(
        db,
        _service_checkpoint(seq=1, active_ms=200),
        _user_identity(telemetry_context.other_user.id),
        country="US",
        user_agent="Mozilla/5.0",
    )
    cross_reader = _stored_row(db)
    assert tuple(getattr(cross_reader, column.name) for column in columns) == before

    assert not svc.record_checkpoint(
        db,
        _service_checkpoint(review_id=telemetry_context.other_review.id, seq=1, active_ms=200),
        _user_identity(),
        country="US",
        user_agent="Mozilla/5.0",
    )
    cross_review = _stored_row(db)
    assert tuple(getattr(cross_review, column.name) for column in columns) == before


@requires_db
def test_the_seventeenth_checkpoint_is_refused(db, telemetry_context):
    for seq in range(16):
        assert svc.record_checkpoint(
            db,
            _service_checkpoint(seq=seq, active_ms=100 + seq, wall_ms=200 + seq),
            _user_identity(),
            country=None,
            user_agent=None,
        )

    row = _stored_row(db)
    assert row.checkpoints == 16
    assert row.max_seq == 15
    columns, before = _row_snapshot(row)

    assert not svc.record_checkpoint(
        db,
        _service_checkpoint(seq=16, active_ms=999, wall_ms=999, scroll_pct=100),
        _user_identity(),
        country="US",
        user_agent="Mozilla/5.0",
    )
    refused = _stored_row(db)
    assert tuple(getattr(refused, column.name) for column in columns) == before


@requires_db
def test_interaction_markers_are_first_occurrence_wins(db, telemetry_context):
    assert svc.record_checkpoint(
        db,
        _service_checkpoint(
            vote_after_ms=2_147_483_647,
            report_after_ms=200,
            comment_after_ms=300,
            share_after_ms=400,
            photo_after_ms=500,
            outlink_after_ms=600,
        ),
        _user_identity(),
        country=None,
        user_agent=None,
    )
    assert svc.record_checkpoint(
        db,
        _service_checkpoint(
            seq=1,
            vote_after_ms=101,
            report_after_ms=201,
            comment_after_ms=301,
            share_after_ms=401,
            photo_after_ms=501,
            outlink_after_ms=601,
        ),
        _user_identity(),
        country=None,
        user_agent=None,
    )

    row = _stored_row(db)
    assert row.vote_client_after_ms == svc.MAX_SESSION_MS
    assert row.report_client_after_ms == 200
    assert row.comment_client_after_ms == 300
    assert row.share_client_after_ms == 400
    assert row.photo_client_after_ms == 500
    assert row.outlink_client_after_ms == 600
    assert row.clamped is True


@requires_db
def test_server_clamps_active_time_to_elapsed_time(db, telemetry_context):
    assert svc.record_checkpoint(
        db,
        _service_checkpoint(active_ms=1_800_000, body_active_ms=1_800_000),
        _user_identity(),
        country=None,
        user_agent=None,
    )

    row = _stored_row(db)
    assert row.active_ms <= svc.SKEW_TOLERANCE_MS
    assert row.body_active_ms <= row.active_ms
    assert row.clamped is True


@requires_db
def test_delete_between_elapsed_read_and_upsert_gets_fresh_insert_clamp(
    db, telemetry_context
):
    assert svc.record_checkpoint(
        db,
        _service_checkpoint(active_ms=0, body_active_ms=0, wall_ms=0),
        _user_identity(),
        country=None,
        user_agent=None,
    )
    db.execute(
        update(ReviewReadingSession)
        .where(ReviewReadingSession.impression_id == IMPRESSION_ID)
        .values(started_at=datetime.now(UTC) - timedelta(hours=1))
    )
    db.commit()

    engine = db.get_bind()
    deleted = False

    def delete_conflict_before_insert(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ):
        nonlocal deleted
        if deleted or not statement.lstrip().startswith(
            "INSERT INTO review_reading_sessions"
        ):
            return
        deleted = True
        with engine.begin() as connection:
            connection.execute(
                delete(ReviewReadingSession).where(
                    ReviewReadingSession.impression_id == IMPRESSION_ID
                )
            )

    event.listen(engine, "before_cursor_execute", delete_conflict_before_insert)
    try:
        assert svc.record_checkpoint(
            db,
            _service_checkpoint(
                seq=1,
                active_ms=svc.MAX_SESSION_MS,
                body_active_ms=svc.MAX_SESSION_MS,
                wall_ms=svc.MAX_SESSION_MS,
            ),
            _user_identity(telemetry_context.user.id),
            country=None,
            user_agent=None,
        )
    finally:
        event.remove(engine, "before_cursor_execute", delete_conflict_before_insert)

    row = _stored_row(db)
    assert deleted is True
    assert row.checkpoints == 1
    assert row.max_seq == 1
    assert row.active_ms <= svc.SKEW_TOLERANCE_MS
    assert row.body_active_ms <= row.active_ms
    assert row.clamped is True


@requires_db
def test_89_day_elapsed_checkpoint_avoids_overflow_and_stays_monotonic(
    db, telemetry_context
):
    assert svc.record_checkpoint(
        db,
        _service_checkpoint(active_ms=100, body_active_ms=80, wall_ms=200),
        _user_identity(),
        country=None,
        user_agent=None,
    )
    db.execute(
        update(ReviewReadingSession)
        .where(ReviewReadingSession.impression_id == IMPRESSION_ID)
        .values(started_at=datetime.now(UTC) - timedelta(days=89))
    )
    db.commit()

    assert svc.record_checkpoint(
        db,
        _service_checkpoint(
            seq=1,
            active_ms=svc.MAX_SESSION_MS,
            body_active_ms=svc.MAX_SESSION_MS,
            wall_ms=svc.MAX_SESSION_MS,
            scroll_pct=100,
        ),
        _user_identity(telemetry_context.user.id),
        country=None,
        user_agent=None,
    )

    row = _stored_row(db)
    assert row.active_ms == svc.MAX_SESSION_MS
    assert row.body_active_ms == svc.MAX_SESSION_MS
    assert row.wall_ms == svc.MAX_SESSION_MS
    assert row.scroll_milestone == 100
    assert row.checkpoints == 2
    assert row.max_seq == 1
    assert row.clamped is False


def test_elapsed_clamp_uses_non_overflowing_postgresql_arithmetic():
    compiled_sql = ""

    class CompilingSession:
        def get(self, _model, _key):
            return SimpleNamespace(discussion="Four literal words here.", star_rating=4)

        def execute(self, statement):
            nonlocal compiled_sql
            compiled_sql = str(statement.compile(dialect=postgresql.dialect()))
            return SimpleNamespace(scalar_one_or_none=lambda: None)

        def commit(self):
            raise AssertionError("a zero-row UPSERT must not commit")

    assert not svc.record_checkpoint(
        CompilingSession(),
        _service_checkpoint(
            seq=1,
            active_ms=svc.MAX_SESSION_MS,
            body_active_ms=svc.MAX_SESSION_MS,
            wall_ms=svc.MAX_SESSION_MS,
        ),
        _user_identity(),
        country=None,
        user_agent=None,
    )

    elapsed_cast = compiled_sql.index("CAST(floor(EXTRACT(epoch")
    elapsed_suffix = compiled_sql[elapsed_cast : elapsed_cast + 250]
    assert "AS BIGINT" in elapsed_suffix
    assert elapsed_suffix.index("AS BIGINT") < elapsed_suffix.index("AS INTEGER")
    # `review_reading_sessions.id` is server-generated, so this upsert must
    # explicitly RETURNING it -- that scalar, not rowcount, is how
    # record_checkpoint below decides whether a row actually changed.
    assert "RETURNING review_reading_sessions.id" in compiled_sql


def test_record_checkpoint_reads_the_returned_id_not_rowcount():
    """A completed PostgreSQL upsert reports success via the row RETURNING
    hands back, not via `CursorResult.rowcount`.

    `review_reading_sessions.id` is server-generated, so SQLAlchemy's
    postgresql dialect attaches a RETURNING clause to this table's INSERT
    regardless of intent. Per SQLAlchemy's own docs, rowcount for a
    RETURNING statement is unreliable (commonly -1) unless the caller opts
    in with the `preserve_rowcount` execution option -- and that option was
    only added in SQLAlchemy 2.0.28, newer than this project's declared
    `sqlalchemy>=2.0,<2.1` floor, and remains DBAPI-dependent even where it
    exists. `FakeResult` below deliberately has no `rowcount` attribute at
    all: a correct implementation never touches it.
    """

    class FakeResult:
        def scalar_one_or_none(self):
            return uuid.uuid4()

    class CompilingSession:
        def get(self, _model, _key):
            return SimpleNamespace(discussion="Four literal words here.", star_rating=4)

        def execute(self, statement):
            return FakeResult()

        def commit(self):
            pass

    assert svc.record_checkpoint(
        CompilingSession(),
        _service_checkpoint(),
        _user_identity(),
        country=None,
        user_agent=None,
    )


@requires_db
def test_replay_noop_does_not_commit(db, telemetry_context, monkeypatch):
    checkpoint = _service_checkpoint(seq=4)
    assert svc.record_checkpoint(
        db, checkpoint, _user_identity(), country=None, user_agent=None
    )

    commits = 0
    real_commit = db.commit

    def track_commit():
        nonlocal commits
        commits += 1
        real_commit()

    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", track_commit)
        assert not svc.record_checkpoint(
            db, checkpoint, _user_identity(), country=None, user_agent=None
        )

    assert commits == 0


@pytest.mark.parametrize(
    ("configured_key", "presented_key"),
    [
        ("test-telemetry-ingest-key", None),
        ("test-telemetry-ingest-key", "wrong-key"),
        ("", ""),
    ],
)
@requires_db
def test_missing_or_wrong_server_key_returns_401_and_writes_zero_rows(
    client,
    db,
    telemetry_context,
    monkeypatch,
    configured_key,
    presented_key,
):
    monkeypatch.setattr(settings, "telemetry_ingest_key", configured_key)
    headers = {"X-Reader-Anon": str(ANON_ID)}
    if presented_key is not None:
        headers["X-Telemetry-Key"] = presented_key

    response = client.post(
        "/api/v1/internal/reading-telemetry",
        headers=headers,
        json=_http_payload(),
    )

    assert response.status_code == 401
    assert _stored_row(db) is None


@requires_db
@pytest.mark.parametrize("anon_header", [str(ANON_ID), "not-a-uuid"])
def test_valid_bearer_with_anon_header_stores_only_the_user(
    client, db, telemetry_context, monkeypatch, anon_header
):
    monkeypatch.setattr(settings, "telemetry_ingest_key", "test-telemetry-ingest-key")
    token = create_access_token(telemetry_context.user.id, "user")

    response = client.post(
        "/api/v1/internal/reading-telemetry",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Reader-Anon": anon_header,
            "X-Reader-Country": "ph",
            "X-Telemetry-Key": "test-telemetry-ingest-key",
            "User-Agent": "Mozilla/5.0 (iPhone; Mobile)",
        },
        json=_http_payload(),
    )

    assert response.status_code == 204
    row = _stored_row(db)
    assert row.reader_kind == ReaderKind.user
    assert row.reader_ref == telemetry_context.user.id
    assert row.anon_ref is None
    assert row.country == "PH"
    assert row.device_class == 1


@pytest.mark.parametrize("authorization", [None, "Bearer not-a-valid-token"])
@requires_db
def test_valid_anon_header_without_bearer_stores_only_the_pseudonym(
    client, db, telemetry_context, monkeypatch, authorization
):
    monkeypatch.setattr(settings, "telemetry_ingest_key", "test-telemetry-ingest-key")

    headers = {
        "X-Reader-Anon": str(ANON_ID),
        "X-Telemetry-Key": "test-telemetry-ingest-key",
    }
    if authorization is not None:
        headers["Authorization"] = authorization

    response = client.post(
        "/api/v1/internal/reading-telemetry",
        headers=headers,
        json=_http_payload(),
    )

    assert response.status_code == 204
    row = _stored_row(db)
    assert row.reader_kind == ReaderKind.anon
    assert row.reader_ref is None
    assert row.anon_ref == ANON_ID


def test_body_identity_fields_produce_422(client):
    response = client.post(
        "/api/v1/internal/reading-telemetry",
        headers={
            "X-Reader-Anon": str(ANON_ID),
            "X-Telemetry-Key": "test-telemetry-ingest-key",
        },
        json=_http_payload(user_id=str(USER_ID)),
    )

    assert response.status_code == 422


def test_malformed_private_payload_produces_422(client):
    response = client.post(
        "/api/v1/internal/reading-telemetry",
        headers={
            "X-Reader-Anon": str(ANON_ID),
            "X-Telemetry-Key": "test-telemetry-ingest-key",
        },
        json=_http_payload(active_ms="1000"),
    )

    assert response.status_code == 422


def test_private_route_requires_server_derived_identity(client, monkeypatch):
    from app.api.v1.routes import reading_telemetry

    monkeypatch.setattr(settings, "telemetry_ingest_key", "test-telemetry-ingest-key")
    monkeypatch.setattr(reading_telemetry, "enforce_rate_limit", lambda *args, **kwargs: None)

    response = client.post(
        "/api/v1/internal/reading-telemetry",
        headers={"X-Telemetry-Key": "test-telemetry-ingest-key"},
        json=_http_payload(),
    )

    assert response.status_code == 401


def test_non_ascii_server_key_is_rejected_as_unauthorized(monkeypatch):
    from app.api.v1.routes import reading_telemetry
    from app.core.errors import AuthError

    monkeypatch.setattr(settings, "telemetry_ingest_key", "test-telemetry-ingest-key")

    with pytest.raises(AuthError):
        reading_telemetry._require_ingest_key("ÿ")


def test_private_route_propagates_reading_telemetry_rate_limit(client, monkeypatch):
    from app.api.v1.routes import reading_telemetry

    calls = []

    def reject(_request, bucket, *, max_requests, window_seconds):
        calls.append((bucket, max_requests, window_seconds))
        raise RateLimitError("Telemetry limit reached.")

    monkeypatch.setattr(settings, "telemetry_ingest_key", "test-telemetry-ingest-key")
    monkeypatch.setattr(settings, "telemetry_rate_limit_max", 7)
    monkeypatch.setattr(reading_telemetry, "enforce_rate_limit", reject)

    response = client.post(
        "/api/v1/internal/reading-telemetry",
        headers={
            "X-Reader-Anon": str(ANON_ID),
            "X-Telemetry-Key": "test-telemetry-ingest-key",
        },
        json=_http_payload(),
    )

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert calls == [("reading_telemetry", 7, 60)]


@pytest.mark.parametrize("country", ["éé", "１２", "XX", "ZZ", "USA"])
def test_country_normalization_rejects_non_iso_alpha2_shapes(country):
    assert svc._normalize_country(country) is None


def test_private_path_registers_post_but_not_get():
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/internal/reading-telemetry"
    ]
    methods = set().union(*(route.methods or set() for route in routes))

    assert "POST" in methods
    assert "GET" not in methods
