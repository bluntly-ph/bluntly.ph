"""Session PII retention correctness (Architecture §4), plus bounded batched
retention for the reading-telemetry tables (review integrity telemetry phase
1, design §9.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, insert, select

from app.models.enums import ReaderKind, Verdict
from app.models.product import Product
from app.models.review import Review
from app.models.telemetry import ReviewReadingSession
from app.models.traffic import ReviewFirstVoteGeoBucket, ReviewViewBucket
from app.models.user import User
from app.services.pii import due_actions, hash_ip, retention_deadlines
from app.services.retention_service import PURGE_TARGETS, bounded_purge, run_retention_sweep
from tests.conftest import requires_db

BASE = datetime(2026, 1, 1, tzinfo=UTC)

# Predates any real data by decades, so a "no rows past this cutoff" assertion
# holds regardless of what else lives in a shared dev database.
FAR_PAST_CUTOFF = datetime(2000, 1, 1, tzinfo=UTC)

RETENTION_USER_ID = uuid.UUID("90000000-0000-4000-8000-000000000001")
RETENTION_PRODUCT_ID = uuid.UUID("90000000-0000-4000-8000-000000000002")
RETENTION_REVIEW_ID = uuid.UUID("90000000-0000-4000-8000-000000000003")


def test_deadlines_are_30_90_90():
    d = retention_deadlines(BASE)
    assert d["ip_hash_at"] == BASE + timedelta(days=30)
    assert d["ip_delete_at"] == BASE + timedelta(days=90)
    assert d["ua_purge_at"] == BASE + timedelta(days=90)


def test_nothing_due_before_30_days():
    actions = due_actions(clicked_at=BASE, now=BASE + timedelta(days=29),
                          has_user_agent=True, has_raw_ip=True, has_ip_hash=False)
    assert actions == set()


def test_ip_hash_due_at_30_days():
    actions = due_actions(clicked_at=BASE, now=BASE + timedelta(days=30),
                          has_user_agent=True, has_raw_ip=True, has_ip_hash=False)
    assert actions == {"hash_ip"}


def test_full_purge_at_90_days():
    actions = due_actions(clicked_at=BASE, now=BASE + timedelta(days=90),
                          has_user_agent=True, has_raw_ip=False, has_ip_hash=True)
    assert actions == {"delete_ip_hash", "purge_ua"}


def test_hash_ip_is_deterministic_and_irreversible():
    h1 = hash_ip("203.0.113.7", salt="s")
    h2 = hash_ip("203.0.113.7", salt="s")
    assert h1 == h2 and len(h1) == 64 and "203.0.113.7" not in h1
    assert hash_ip("203.0.113.7", salt="other") != h1


def test_bounded_purge_rejects_targets_outside_the_allow_list():
    with pytest.raises(ValueError):
        bounded_purge(None, "users", "created_at", BASE)


def test_purge_targets_allow_list_matches_the_four_telemetry_tables():
    assert PURGE_TARGETS == {
        "review_reading_sessions": "started_at",
        "review_view_buckets": "bucket_start",
        "request_geo_buckets": "bucket_start",
        "review_first_vote_geo_buckets": "bucket_start",
    }


# --- bounded_purge fails closed on out-of-range caller overrides -------------
#
# Validation must happen before any SQL is built, so these pass db=None, same
# as test_bounded_purge_rejects_targets_outside_the_allow_list above. Bounding
# batch_size <= 5,000 and max_batches <= 40 individually also bounds their
# product <= 200,000, which is the architectural per-table-per-run ceiling.


@pytest.mark.parametrize("batch_size", [0, -1, -5000, 5001, 100_000])
def test_bounded_purge_rejects_batch_size_overrides_outside_1_5000(batch_size):
    with pytest.raises(ValueError):
        bounded_purge(
            None, "review_reading_sessions", "started_at", BASE, batch_size=batch_size
        )


@pytest.mark.parametrize("max_batches", [0, -1, -40, 41, 1000])
def test_bounded_purge_rejects_max_batches_overrides_outside_1_40(max_batches):
    with pytest.raises(ValueError):
        bounded_purge(
            None, "review_reading_sessions", "started_at", BASE, max_batches=max_batches
        )


# --- Bounded, batched retention against a real database ---------------------


@pytest.fixture
def retention_review(db):
    """One real review, owned by a real user, for FK-bound telemetry rows."""

    def clean() -> None:
        db.rollback()
        db.execute(delete(ReviewFirstVoteGeoBucket)
                   .where(ReviewFirstVoteGeoBucket.review_id == RETENTION_REVIEW_ID))
        db.execute(delete(ReviewViewBucket)
                   .where(ReviewViewBucket.review_id == RETENTION_REVIEW_ID))
        db.execute(delete(ReviewReadingSession)
                   .where(ReviewReadingSession.review_id == RETENTION_REVIEW_ID))
        db.execute(delete(Review).where(Review.id == RETENTION_REVIEW_ID))
        db.execute(delete(Product).where(Product.id == RETENTION_PRODUCT_ID))
        db.execute(delete(User).where(User.id == RETENTION_USER_ID))
        db.commit()

    clean()
    user = User(
        id=RETENTION_USER_ID,
        email="retention-fixture@example.com",
        username="retention_fixture",
        display_name="Retention Fixture",
    )
    product = Product(id=RETENTION_PRODUCT_ID, canonical_name="Retention Fixture Product")
    review = Review(
        id=RETENTION_REVIEW_ID,
        product_id=RETENTION_PRODUCT_ID,
        author_id=RETENTION_USER_ID,
        title="Retention fixture review",
        discussion="Fixture body for retention tests.",
        verdict=Verdict.it_depends,
        star_rating=4,
    )
    db.add_all([user, product, review])
    db.commit()
    try:
        yield review
    finally:
        clean()


def _insert_reading_rows(db, review_id, started_ats) -> None:
    db.execute(
        insert(ReviewReadingSession),
        [
            {
                "impression_id": uuid.uuid4(),
                "review_id": review_id,
                "reader_kind": ReaderKind.anon,
                "anon_ref": uuid.uuid4(),
                "started_at": started_at,
                "last_seen_at": started_at,
            }
            for started_at in started_ats
        ],
    )
    db.commit()


def _reading_row_count(db, review_id) -> int:
    db.expire_all()
    return len(db.scalars(
        select(ReviewReadingSession.id).where(ReviewReadingSession.review_id == review_id)
    ).all())


@requires_db
def test_bounded_purge_deletes_expired_reading_rows_in_configured_batches(
    db, retention_review
):
    _insert_reading_rows(
        db, retention_review.id, [BASE - timedelta(days=1)] * 5
    )

    result = bounded_purge(
        db, "review_reading_sessions", "started_at", BASE, batch_size=2, max_batches=10
    )

    assert result.deleted == 5
    assert result.ceiling_hit is False
    assert _reading_row_count(db, retention_review.id) == 0


@requires_db
def test_bounded_purge_leaves_in_window_rows(db, retention_review):
    _insert_reading_rows(
        db, retention_review.id,
        [BASE - timedelta(days=1), BASE + timedelta(days=1)],
    )

    result = bounded_purge(db, "review_reading_sessions", "started_at", BASE)

    assert result.deleted == 1
    assert _reading_row_count(db, retention_review.id) == 1


@requires_db
def test_bounded_purge_review_view_buckets_runs_without_ingestion(db):
    result = bounded_purge(
        db, "review_view_buckets", "bucket_start", FAR_PAST_CUTOFF
    )

    assert result == (0, False)


@requires_db
def test_bounded_purge_request_geo_buckets_runs_without_ingestion(db):
    result = bounded_purge(
        db, "request_geo_buckets", "bucket_start", FAR_PAST_CUTOFF
    )

    assert result == (0, False)


@requires_db
def test_bounded_purge_first_vote_geo_is_idempotent(db, retention_review):
    db.execute(insert(ReviewFirstVoteGeoBucket).values(
        review_id=retention_review.id,
        bucket_start=BASE - timedelta(days=1),
        first_vote_count=3,
    ))
    db.commit()

    first = bounded_purge(
        db, "review_first_vote_geo_buckets", "bucket_start", BASE
    )
    second = bounded_purge(
        db, "review_first_vote_geo_buckets", "bucket_start", BASE
    )

    assert first == (1, False)
    assert second == (0, False)


@requires_db
def test_bounded_purge_ceiling_reports_remaining_work_for_the_next_invocation(
    db, retention_review
):
    _insert_reading_rows(
        db, retention_review.id, [BASE - timedelta(days=1)] * 4
    )

    first = bounded_purge(
        db, "review_reading_sessions", "started_at", BASE, batch_size=3, max_batches=1
    )
    assert first == (3, True)
    assert _reading_row_count(db, retention_review.id) == 1

    second = bounded_purge(
        db, "review_reading_sessions", "started_at", BASE, batch_size=3, max_batches=1
    )
    assert second == (1, False)
    assert _reading_row_count(db, retention_review.id) == 0


@requires_db
def test_run_retention_sweep_returns_the_expanded_key_set(db):
    counts = run_retention_sweep(db)

    assert set(counts) == {
        "hashed", "purged", "reading_sessions",
        "review_view_buckets", "request_geo_buckets", "first_vote_geo_buckets",
    }
    assert all(isinstance(v, int) and v >= 0 for v in counts.values())
