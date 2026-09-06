"""Owner-run research export and strict invariant checks (review integrity
telemetry phase 1, design §8/§9.2/§10).

New file rather than an addition to `test_reading_telemetry.py`: that file is
owned by a parallel task in this same phase, and appending here avoids a merge
conflict on it.
"""

from __future__ import annotations

import argparse
import csv
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, func, insert, select, text

import scripts.export_reading_telemetry as export_module
from app.models.enums import ReaderKind, Verdict, VoteDirection
from app.models.product import Product
from app.models.review import Review
from app.models.telemetry import ReviewReadingSession
from app.models.traffic import RequestGeoBucket, ReviewFirstVoteGeoBucket
from app.models.user import User
from app.models.vote import ReviewVote
from app.services.retention_service import bounded_purge
from scripts.check_invariants import CHECKS
from scripts.export_reading_telemetry import (
    MAX_SINCE_DAYS,
    MIN_SINCE_DAYS,
    OutputPathError,
    _open_output,
    _since_days,
    _validate_output_path,
    export_geo_summary,
    export_readings,
    export_relationships,
)
from tests.conftest import requires_db

EXPORT_AUTHOR_ID = uuid.UUID("91000000-0000-4000-8000-000000000001")
EXPORT_VOTER_ID = uuid.UUID("91000000-0000-4000-8000-000000000002")
EXPORT_OTHER_VOTER_ID = uuid.UUID("91000000-0000-4000-8000-000000000003")
EXPORT_PRODUCT_ID = uuid.UUID("91000000-0000-4000-8000-000000000004")
EXPORT_REVIEW_ID = uuid.UUID("91000000-0000-4000-8000-000000000005")
#: A Vercel POP name is at most 8 chars; used only to scope test cleanup.
EXPORT_POP_MARKER = "EXPORT01"


# --- --output validation, no database required ------------------------------


@pytest.mark.parametrize(
    "bad",
    ["-", "/dev/stdout", "/dev/stderr", "/dev/null", "CON", "con", "NUL", "PRN", "AUX"],
)
def test_output_path_rejects_stdout_and_device_names(bad):
    with pytest.raises(OutputPathError):
        _validate_output_path(bad)


@pytest.mark.parametrize(
    "bad",
    [
        # bare names, extensions, case
        "NUL.csv", "nul.csv", "CON.csv", "con.txt", "PRN.csv", "AUX.csv",
        "COM1", "com1.csv", "COM9.csv", "LPT1", "lpt1.csv", "LPT9.csv",
        # console devices matched by literal name (with and without extension)
        "CONOUT$", "conout$", "CONIN$", "conin$", "conin$.csv", "CONOUT$.log",
        # trailing dots/spaces are ignored by Windows when matching a device
        "NUL.", "nul .csv", "  CON  ", "prn...",
        # nested POSIX spellings
        "reports/NUL.csv", "reports/lpt3.log", "a/b/c/AUX",
        # nested Windows spellings -- os.path.basename does NOT split "\\" on
        # Linux CI, so these must be recognised by PureWindowsPath, not os.path
        "reports\\COM1.csv", "a\\b\\CONIN$", "C:\\tmp\\nul.csv",
        # mixed separators
        "reports\\sub/COM2.csv", "reports/sub\\lpt2",
    ],
)
def test_output_path_rejects_reserved_device_names_with_suffixes(bad, tmp_path):
    # Must reject on string inspection alone -- never touch/create the path,
    # since opening a device name like NUL on Windows has a real side effect.
    before = set(tmp_path.iterdir()) if tmp_path.exists() else set()
    with pytest.raises(OutputPathError):
        _validate_output_path(bad)
    after = set(tmp_path.iterdir()) if tmp_path.exists() else set()
    assert before == after


@pytest.mark.parametrize(
    "good",
    [
        "out.csv",
        "reports/computer.csv",        # substring of a device name, not one
        "reports\\common.csv",
        "com10.csv",                   # only com1-9 are reserved
        "lpt0.csv",
        "console.log",
        "nulls.csv",
        "a/b/readings-con.csv",        # device name only as a suffix fragment
    ],
)
def test_output_path_accepts_legitimate_filenames_near_device_names(good):
    assert _validate_output_path(good) == good


def test_output_path_accepts_a_plain_file_path(tmp_path):
    target = tmp_path / "out.csv"
    assert _validate_output_path(str(target)) == str(target)


def test_open_output_refuses_to_overwrite_an_existing_file(tmp_path):
    target = tmp_path / "exists.csv"
    target.write_text("already here", encoding="utf-8")
    with pytest.raises(OutputPathError):
        _open_output(str(target))


@pytest.mark.parametrize("bad", ["0", "91", "-1", "abc"])
def test_since_days_rejects_out_of_range_or_non_integer_values(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        _since_days(bad)


@pytest.mark.parametrize("value", ["1", "30", "90"])
def test_since_days_accepts_the_documented_bounds(value):
    parsed = _since_days(value)
    assert MIN_SINCE_DAYS <= parsed <= MAX_SINCE_DAYS


# --- Fixture: a real author, two voters, and a product ----------------------


@pytest.fixture
def export_fixture(db):
    """Real rows the export modes can query. Reviews are created per-test;
    deleting by `product_id` cascades their votes, reading sessions, and geo
    buckets, so cleanup does not need to track ids it did not create."""

    def clean() -> None:
        db.rollback()
        db.execute(delete(Review).where(Review.product_id == EXPORT_PRODUCT_ID))
        db.execute(delete(RequestGeoBucket).where(RequestGeoBucket.pop == EXPORT_POP_MARKER))
        db.execute(delete(Product).where(Product.id == EXPORT_PRODUCT_ID))
        db.execute(delete(User).where(
            User.id.in_([EXPORT_AUTHOR_ID, EXPORT_VOTER_ID, EXPORT_OTHER_VOTER_ID])))
        db.commit()

    clean()
    author = User(id=EXPORT_AUTHOR_ID, email="export-author@example.com",
                  username="export_author", display_name="Export Author")
    voter = User(id=EXPORT_VOTER_ID, email="export-voter@example.com",
                 username="export_voter", display_name="Export Voter")
    other_voter = User(id=EXPORT_OTHER_VOTER_ID, email="export-other-voter@example.com",
                       username="export_other_voter", display_name="Export Other Voter")
    product = Product(id=EXPORT_PRODUCT_ID, canonical_name="Export Fixture Product")
    db.add_all([author, voter, other_voter, product])
    db.commit()
    try:
        yield SimpleNamespace(author=author, voter=voter, other_voter=other_voter, product=product)
    finally:
        clean()


# --- Step 4, case 1: export writes only its named file and no database row --


@requires_db
def test_export_readings_writes_only_the_named_file_and_touches_no_row(
    db, export_fixture, tmp_path
):
    review = Review(
        id=EXPORT_REVIEW_ID, product_id=EXPORT_PRODUCT_ID, author_id=EXPORT_AUTHOR_ID,
        title="Export fixture review", discussion="Body text for the export fixture.",
        verdict=Verdict.it_depends, star_rating=5,
    )
    db.add(review)
    db.commit()

    started_at = datetime.now(UTC) - timedelta(days=1)
    db.execute(insert(ReviewReadingSession).values(
        impression_id=uuid.uuid4(), review_id=EXPORT_REVIEW_ID,
        reader_kind=ReaderKind.anon, anon_ref=uuid.uuid4(),
        started_at=started_at, last_seen_at=started_at,
        active_ms=12345, body_active_ms=10000, wall_ms=15000,
        scroll_milestone=75, checkpoints=3, clamped=False,
        country="PH", word_count_at_view=42, star_rating_at_view=5, device_class=1,
    ))
    db.commit()

    before_sessions = db.scalar(select(func.count()).select_from(ReviewReadingSession))
    before_reviews = db.scalar(select(func.count()).select_from(Review))

    out_path = tmp_path / "readings.csv"
    result = export_readings(db, str(out_path), since_days=7)

    assert db.scalar(select(func.count()).select_from(ReviewReadingSession)) == before_sessions
    assert db.scalar(select(func.count()).select_from(Review)) == before_reviews

    assert list(tmp_path.iterdir()) == [out_path]
    assert result.rows_written == 1

    with open(out_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == export_module.READINGS_HEADER
    data = dict(zip(rows[0], rows[1], strict=True))
    assert data["review_id"] == str(EXPORT_REVIEW_ID)
    assert data["reader_kind"] == "anon"
    assert data["country"] == "PH"
    assert data["active_ms"] == "12345"
    assert data["word_count_at_view"] == "42"
    assert "reader_ref" not in rows[0] and "anon_ref" not in rows[0]


# --- Step 4, case 2: relationship export ignores the 31st-older review ------


@requires_db
def test_relationship_export_ignores_an_authors_31st_older_review(
    db, export_fixture, tmp_path
):
    now = datetime.now(UTC)
    review_ids = [uuid.uuid4() for _ in range(31)]
    reviews = [
        Review(
            id=review_id, product_id=EXPORT_PRODUCT_ID, author_id=EXPORT_AUTHOR_ID,
            title=f"Relationship fixture review {index}", discussion="Body text.",
            verdict=Verdict.it_depends, star_rating=4,
            # index 0 is published longest ago; it is the 31st-most-recent and
            # therefore the one outside the 30-review window.
            published_at=now - timedelta(days=31 - index),
        )
        for index, review_id in enumerate(review_ids)
    ]
    db.add_all(reviews)
    db.commit()

    oldest_review_id = review_ids[0]
    db.execute(insert(ReviewVote).values(
        review_id=oldest_review_id, voter_id=EXPORT_VOTER_ID, vote=VoteDirection.up,
    ))
    db.commit()

    out_path = tmp_path / "relationships.csv"
    result = export_relationships(db, str(out_path), since_days=90)

    with open(out_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == export_module.RELATIONSHIPS_HEADER
    assert rows[1:] == []
    assert result.rows_written == 0


@requires_db
def test_relationship_export_excludes_an_authors_review_outside_the_since_days_window(
    db, export_fixture, tmp_path
):
    """An author qualifies via one recent review, but a second, older review of
    theirs (outside --since-days, though still inside the 90-day retention
    horizon) must not be pulled into the bounded 30-review window just because
    the author has activity -- and its vote must not be tallied either."""
    now = datetime.now(UTC)
    recent_review_id = uuid.uuid4()
    old_review_id = uuid.uuid4()
    reviews = [
        Review(
            id=recent_review_id, product_id=EXPORT_PRODUCT_ID, author_id=EXPORT_AUTHOR_ID,
            title="Recent review", discussion="Body text.",
            verdict=Verdict.it_depends, star_rating=4,
            published_at=now - timedelta(days=1),
        ),
        Review(
            id=old_review_id, product_id=EXPORT_PRODUCT_ID, author_id=EXPORT_AUTHOR_ID,
            title="Old review outside the since-days window", discussion="Body text.",
            verdict=Verdict.it_depends, star_rating=4,
            published_at=now - timedelta(days=20),
        ),
    ]
    db.add_all(reviews)
    db.commit()
    db.execute(insert(ReviewVote).values(
        review_id=old_review_id, voter_id=EXPORT_VOTER_ID, vote=VoteDirection.up,
    ))
    db.commit()

    out_path = tmp_path / "relationships.csv"
    result = export_relationships(db, str(out_path), since_days=7)

    with open(out_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[1:] == []
    assert result.rows_written == 0


@requires_db
def test_relationship_export_excludes_a_vote_cast_before_the_since_days_window(
    db, export_fixture, tmp_path
):
    """The review itself is inside the window, but its vote's own creation
    timestamp is not -- the tally must be bound by vote `created_at`, not only
    by the parent review's `published_at`."""
    now = datetime.now(UTC)
    review = Review(
        id=EXPORT_REVIEW_ID, product_id=EXPORT_PRODUCT_ID, author_id=EXPORT_AUTHOR_ID,
        title="In-window review with a stale vote", discussion="Body text.",
        verdict=Verdict.it_depends, star_rating=4, published_at=now - timedelta(days=1),
    )
    db.add(review)
    db.commit()
    db.execute(insert(ReviewVote).values(
        review_id=EXPORT_REVIEW_ID, voter_id=EXPORT_VOTER_ID, vote=VoteDirection.up,
        created_at=now - timedelta(days=20),
    ))
    db.commit()

    out_path = tmp_path / "relationships.csv"
    result = export_relationships(db, str(out_path), since_days=7)

    with open(out_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[1:] == []
    assert result.rows_written == 0


@requires_db
def test_relationship_export_counts_a_vote_inside_the_window(
    db, export_fixture, tmp_path
):
    now = datetime.now(UTC)
    review = Review(
        id=EXPORT_REVIEW_ID, product_id=EXPORT_PRODUCT_ID, author_id=EXPORT_AUTHOR_ID,
        title="Relationship in-window review", discussion="Body text.",
        verdict=Verdict.it_depends, star_rating=4, published_at=now - timedelta(days=1),
    )
    db.add(review)
    db.commit()
    db.execute(insert(ReviewVote).values(
        review_id=EXPORT_REVIEW_ID, voter_id=EXPORT_VOTER_ID, vote=VoteDirection.up,
    ))
    db.commit()

    out_path = tmp_path / "relationships.csv"
    result = export_relationships(db, str(out_path), since_days=90)

    with open(out_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert result.rows_written == 1
    data = dict(zip(rows[0], rows[1], strict=True))
    assert data["author_id"] == str(EXPORT_AUTHOR_ID)
    assert data["voter_id"] == str(EXPORT_VOTER_ID)
    assert data["voted"] == "1"
    assert data["eligible"] == "1"


# --- Step 4, case 3: geography export uses aggregates, no voter identity ----


@requires_db
def test_geo_summary_export_uses_aggregate_columns_without_voter_identity(
    db, export_fixture, tmp_path
):
    review = Review(
        id=EXPORT_REVIEW_ID, product_id=EXPORT_PRODUCT_ID, author_id=EXPORT_AUTHOR_ID,
        title="Geo fixture review", discussion="Body text.",
        verdict=Verdict.it_depends, star_rating=3,
    )
    db.add(review)
    db.commit()

    bucket = (datetime.now(UTC) - timedelta(hours=2)).replace(
        minute=0, second=0, microsecond=0)
    db.execute(insert(ReviewFirstVoteGeoBucket).values(
        review_id=EXPORT_REVIEW_ID, bucket_start=bucket,
        country="PH", region="Metro Manila", city="Manila", first_vote_count=4,
    ))
    db.execute(insert(RequestGeoBucket).values(
        bucket_start=bucket, country="PH", region="Metro Manila", city="Manila",
        pop=EXPORT_POP_MARKER, request_count=40,
    ))
    db.commit()

    out_path = tmp_path / "geo.csv"
    export_geo_summary(db, str(out_path), since_days=7)

    with open(out_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == export_module.GEO_SUMMARY_HEADER
    assert not {"voter_id", "reader_ref", "anon_ref", "user_id"} & set(rows[0])
    match = next(r for r in rows[1:] if r[:3] == ["PH", "Metro Manila", "Manila"])
    assert match == ["PH", "Metro Manila", "Manila", "4", "40"]


# --- Step 4, case 4: strict invariants identify dual/no identity + expired --


def _check_sql(name: str) -> str:
    for check_name, sql, _meaning in CHECKS:
        if check_name == name:
            return sql
    raise AssertionError(f"no invariant check named {name!r}")


@requires_db
def test_strict_invariants_identify_no_identity_violations_on_compliant_data(db):
    """`ck_reading_reader_user/anon` makes a dual/no-identity row unreachable
    through the ORM or a normal INSERT, so this proves the check's SQL is
    correct against compliant data rather than provoking an impossible row."""
    sql = _check_sql("reading sessions with dual or missing reader identity")
    assert db.execute(text(sql)).scalar() == 0


@requires_db
def test_strict_invariants_identify_rows_past_the_retention_cutoff(
    db, export_fixture
):
    sql = _check_sql("reading sessions past the retention cutoff")

    review = Review(
        id=EXPORT_REVIEW_ID, product_id=EXPORT_PRODUCT_ID, author_id=EXPORT_AUTHOR_ID,
        title="Invariant fixture review", discussion="Body text.",
        verdict=Verdict.it_depends, star_rating=2,
    )
    db.add(review)
    db.commit()

    expired_at = datetime.now(UTC) - timedelta(days=91)
    db.execute(insert(ReviewReadingSession).values(
        impression_id=uuid.uuid4(), review_id=EXPORT_REVIEW_ID,
        reader_kind=ReaderKind.anon, anon_ref=uuid.uuid4(),
        started_at=expired_at, last_seen_at=expired_at,
    ))
    db.commit()

    assert db.execute(text(sql)).scalar() >= 1

    bounded_purge(db, "review_reading_sessions", "started_at",
                  datetime.now(UTC) - timedelta(days=90))

    assert db.execute(text(sql)).scalar() == 0
