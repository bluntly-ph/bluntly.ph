"""Task 8 — server-authoritative vote timing and first-vote geography.

Crosses three services (`vote_service`, `reading_telemetry_service`,
`request_traffic_service`) at the route in `reviews.py`, so it lives in its
own module rather than any one of theirs — see task-8-worker-instructions.md.

Nothing here feeds scoring, payout, ranking, moderation, or publication; that
isolation is asserted in `tests/test_telemetry_isolation.py`. This module only
asserts the new write-only tail: `created` semantics, first-occurrence-wins
timing, fail-open safety, and that the geography aggregate never carries a
voter identity.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.dialects import postgresql

from app.core.security import create_access_token
from app.models.enums import ReaderKind, Verdict, VoteDirection
from app.models.product import Product
from app.models.review import Review
from app.models.telemetry import ReviewReadingSession
from app.models.traffic import ReviewFirstVoteGeoBucket
from app.models.user import User
from app.models.vote import ReviewVote
from app.services import reading_telemetry_service, request_traffic_service, vote_service
from app.services.request_geo import RequestGeo
from tests.conftest import requires_db

AUTHOR_ID = uuid.UUID("60000000-0000-4000-8000-000000000001")
VOTER_ID = uuid.UUID("60000000-0000-4000-8000-000000000002")
PRODUCT_ID = uuid.UUID("60000000-0000-4000-8000-000000000003")
REVIEW_ID = uuid.UUID("60000000-0000-4000-8000-000000000004")


@pytest.fixture
def vote_context(db):
    """A published review with a real author and a real, distinct voter.

    Deletes by exact id, same shape as `telemetry_context` in
    test_reading_telemetry.py: deleting the product cascades to the review,
    which cascades to its votes, reading sessions, and first-vote-geo buckets
    (all `ondelete="CASCADE"` on `review_id`), so only the two users need a
    second delete.
    """

    def clean() -> None:
        db.rollback()
        db.execute(delete(Product).where(Product.id == PRODUCT_ID))
        db.execute(delete(User).where(User.id.in_([AUTHOR_ID, VOTER_ID])))
        db.commit()

    clean()
    author = User(
        id=AUTHOR_ID,
        email="vote-telemetry-author@example.com",
        username="vote_telemetry_author",
        display_name="Vote Telemetry Author",
    )
    voter = User(
        id=VOTER_ID,
        email="vote-telemetry-voter@example.com",
        username="vote_telemetry_voter",
        display_name="Vote Telemetry Voter",
    )
    product = Product(id=PRODUCT_ID, canonical_name="Vote Telemetry Fixture Product")
    # Flushed before the review is constructed. `Review.author_id`/
    # `product_id` are bare FK columns with no declared `relationship()`, so
    # SQLAlchemy's unit-of-work has no dependency edge forcing `users`/
    # `products` to insert before `reviews` — batching all four objects into
    # one `add_all`/`commit` lets it flush them in the wrong order and fail
    # with a FK violation on a genuinely empty table. Flushing the parents
    # first (the pattern `make_user` + `test_affiliate_ingest.py` already use
    # elsewhere in this suite) sidesteps the ordering question entirely.
    db.add_all([author, voter, product])
    db.flush()
    review = Review(
        id=REVIEW_ID,
        product_id=PRODUCT_ID,
        author_id=AUTHOR_ID,
        title="Vote telemetry fixture review",
        discussion="A fixture review body used by the vote telemetry tests.",
        verdict=Verdict.it_depends,
        star_rating=4,
        published_at=datetime.now(UTC) - timedelta(days=1),
    )
    db.add(review)
    db.commit()
    try:
        yield SimpleNamespace(author=author, voter=voter, review=review)
    finally:
        clean()


def _user_identity(user_id):
    return reading_telemetry_service.ReaderIdentity(kind=ReaderKind.user, reader_ref=user_id)


def _checkpoint(review_id, **overrides):
    payload = {
        "impression_id": uuid.uuid4(),
        "review_id": review_id,
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
    return reading_telemetry_service.CheckpointData(**payload)


def _row(db, impression_id):
    db.expire_all()
    return db.scalar(
        select(ReviewReadingSession).where(
            ReviewReadingSession.impression_id == impression_id
        )
    )


# ---------------------------------------------------------------------------
# `created` — exactly first-insert semantics
# ---------------------------------------------------------------------------

@requires_db
def test_created_is_true_only_on_first_insert_and_false_on_retry_or_change(
    db, vote_context
):
    first = vote_service.cast_vote(
        db, vote_context.review, vote_context.voter, VoteDirection.up
    )
    assert first.created is True

    retry = vote_service.cast_vote(
        db, vote_context.review, vote_context.voter, VoteDirection.up
    )
    assert retry.created is False

    changed = vote_service.cast_vote(
        db, vote_context.review, vote_context.voter, VoteDirection.down
    )
    assert changed.created is False

    n = db.scalar(
        select(ReviewVote)
        .where(
            ReviewVote.review_id == vote_context.review.id,
            ReviewVote.voter_id == vote_context.voter.id,
        )
    )
    assert n is not None  # one upserted row, not three


# ---------------------------------------------------------------------------
# note_vote — latest still-open impression, first-occurrence-wins
# ---------------------------------------------------------------------------

@requires_db
def test_note_vote_stamps_only_the_latest_still_open_impression(db, vote_context):
    older = _checkpoint(vote_context.review.id)
    assert reading_telemetry_service.record_checkpoint(
        db, older, _user_identity(vote_context.voter.id), country=None, user_agent=None
    )
    db.execute(
        update(ReviewReadingSession)
        .where(ReviewReadingSession.impression_id == older.impression_id)
        .values(started_at=datetime.now(UTC) - timedelta(minutes=25))
    )
    db.commit()

    newer = _checkpoint(vote_context.review.id)
    assert reading_telemetry_service.record_checkpoint(
        db, newer, _user_identity(vote_context.voter.id), country=None, user_agent=None
    )

    assert reading_telemetry_service.note_vote(
        db, vote_context.review.id, vote_context.voter.id
    )

    older_row = _row(db, older.impression_id)
    newer_row = _row(db, newer.impression_id)
    assert older_row.first_vote_at is None
    assert newer_row.first_vote_at is not None
    assert newer_row.active_ms_at_first_vote == newer_row.active_ms


@requires_db
def test_note_vote_excludes_a_session_older_than_thirty_minutes(db, vote_context):
    expired = _checkpoint(vote_context.review.id)
    assert reading_telemetry_service.record_checkpoint(
        db, expired, _user_identity(vote_context.voter.id), country=None, user_agent=None
    )
    db.execute(
        update(ReviewReadingSession)
        .where(ReviewReadingSession.impression_id == expired.impression_id)
        .values(started_at=datetime.now(UTC) - timedelta(minutes=31))
    )
    db.commit()

    assert not reading_telemetry_service.note_vote(
        db, vote_context.review.id, vote_context.voter.id
    )
    assert _row(db, expired.impression_id).first_vote_at is None


@requires_db
def test_note_vote_ignores_unrelated_and_anonymous_sessions(db, vote_context):
    other_reader = _checkpoint(vote_context.review.id)
    assert reading_telemetry_service.record_checkpoint(
        db, other_reader, _user_identity(vote_context.author.id), country=None,
        user_agent=None,
    )
    anon = _checkpoint(vote_context.review.id)
    assert reading_telemetry_service.record_checkpoint(
        db, anon,
        reading_telemetry_service.ReaderIdentity(kind=ReaderKind.anon, anon_ref=uuid.uuid4()),
        country=None, user_agent=None,
    )

    assert not reading_telemetry_service.note_vote(
        db, vote_context.review.id, vote_context.voter.id
    )
    assert _row(db, other_reader.impression_id).first_vote_at is None
    assert _row(db, anon.impression_id).first_vote_at is None


@requires_db
def test_note_vote_preserves_the_original_snapshot_across_repeated_votes(
    db, vote_context
):
    checkpoint = _checkpoint(vote_context.review.id, active_ms=100, body_active_ms=80)
    assert reading_telemetry_service.record_checkpoint(
        db, checkpoint, _user_identity(vote_context.voter.id), country=None,
        user_agent=None,
    )

    assert reading_telemetry_service.note_vote(
        db, vote_context.review.id, vote_context.voter.id
    )
    first_row = _row(db, checkpoint.impression_id)
    original_timestamp = first_row.first_vote_at
    original_active = first_row.active_ms_at_first_vote
    assert original_active == 100

    # A later checkpoint advances activity — simulating time passing after the
    # first vote — then a second vote (a direction change) calls note_vote again.
    later = _checkpoint(
        vote_context.review.id,
        impression_id=checkpoint.impression_id,
        seq=1,
        active_ms=4_000,
        body_active_ms=3_000,
    )
    assert reading_telemetry_service.record_checkpoint(
        db, later, _user_identity(vote_context.voter.id), country=None, user_agent=None
    )
    assert reading_telemetry_service.note_vote(
        db, vote_context.review.id, vote_context.voter.id
    )

    second_row = _row(db, checkpoint.impression_id)
    assert second_row.active_ms > original_active  # the session really did advance
    assert second_row.first_vote_at == original_timestamp
    assert second_row.active_ms_at_first_vote == original_active  # not overwritten


def test_note_vote_query_uses_the_thirty_minute_window_and_coalesce_without_a_database():
    """Compiles the real statement against the PostgreSQL dialect rather than
    executing it, so this runs even where Postgres is unavailable — see
    the analogous `test_elapsed_clamp_...` check in test_reading_telemetry.py.
    """
    compiled_sql = ""

    class CompilingSession:
        def execute(self, statement):
            nonlocal compiled_sql
            compiled_sql = str(statement.compile(dialect=postgresql.dialect()))
            return SimpleNamespace(rowcount=0)

        def commit(self):
            pass

        def rollback(self):
            raise AssertionError("a dry compile must not need to roll back")

    changed = reading_telemetry_service.note_vote(
        CompilingSession(), uuid.uuid4(), uuid.uuid4()
    )

    assert changed is False
    lowered = compiled_sql.lower()
    assert "interval '30 minutes'" in lowered
    assert "coalesce" in lowered
    assert "reader_kind" in lowered


# ---------------------------------------------------------------------------
# The route: fail-open telemetry, and the aggregate's created-only gate
# ---------------------------------------------------------------------------

def _auth(user_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id, 'user')}"}


@requires_db
def test_a_forced_telemetry_exception_still_leaves_the_vote_and_wilson_committed(
    client, db, vote_context, monkeypatch
):
    from app.api.v1.routes import reviews as reviews_route

    def boom(*_args, **_kwargs):
        raise RuntimeError("telemetry exploded")

    monkeypatch.setattr(reviews_route.reading_telemetry_service, "note_vote", boom)
    monkeypatch.setattr(
        reviews_route.request_traffic_service, "record_first_vote_geo", boom
    )

    response = client.post(
        f"/api/v1/reviews/{vote_context.review.id}/vote",
        headers=_auth(vote_context.voter.id),
        json={"vote": "up"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["helpful_votes"], body["unhelpful_votes"]) == (1, 0)
    assert float(body["wilson_score"]) > 0

    db.expire_all()
    stored_vote = db.scalar(
        select(ReviewVote).where(
            ReviewVote.review_id == vote_context.review.id,
            ReviewVote.voter_id == vote_context.voter.id,
        )
    )
    assert stored_vote is not None
    assert stored_vote.vote == VoteDirection.up


@requires_db
def test_a_rollback_expired_review_object_does_not_crash_the_tail(
    client, db, vote_context, monkeypatch
):
    """Reviewer-verified fail-open gap: `note_vote` catches its own errors and
    rolls back internally (it never raises), which expires every ORM object
    in the route's session — including `result.review`. The old route code
    still dereferenced `result.review.id` after that for the geo tail and its
    log line, so a persistent DB failure there could turn an already-committed
    vote into a 500. This reproduces that by rolling back *and* detaching the
    review object, which makes any further attribute access raise
    `DetachedInstanceError` without needing a real DB outage — proving the
    route no longer needs to touch the ORM object once a tail has run.
    """
    from app.api.v1.routes import reviews as reviews_route

    def rollback_and_detach_review(session, review_id, _reader_id):
        session.rollback()
        obj = session.get(Review, review_id)
        if obj is not None:
            session.expunge(obj)
        return False

    monkeypatch.setattr(
        reviews_route.reading_telemetry_service, "note_vote", rollback_and_detach_review
    )

    geo_headers = {
        "x-vercel-ip-country": "PH",
        "x-vercel-ip-country-region": "NCR",
        "x-vercel-ip-city": "Manila",
    }
    response = client.post(
        f"/api/v1/reviews/{vote_context.review.id}/vote",
        headers={**_auth(vote_context.voter.id), **geo_headers},
        json={"vote": "up"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["helpful_votes"], body["unhelpful_votes"]) == (1, 0)
    assert float(body["wilson_score"]) > 0

    db.expire_all()
    stored_vote = db.scalar(
        select(ReviewVote).where(
            ReviewVote.review_id == vote_context.review.id,
            ReviewVote.voter_id == vote_context.voter.id,
        )
    )
    assert stored_vote is not None
    assert stored_vote.vote == VoteDirection.up

    # The geo tail runs after note_vote, in the `if result.created:` branch —
    # it must still fire (and succeed) even though the review object was
    # detached by the first tail, because it only ever needs the plain id.
    geo_rows = db.execute(
        select(ReviewFirstVoteGeoBucket).where(
            ReviewFirstVoteGeoBucket.review_id == vote_context.review.id
        )
    ).scalars().all()
    assert len(geo_rows) == 1
    assert geo_rows[0].first_vote_count == 1


@requires_db
def test_first_vote_geo_increments_only_on_the_creating_vote(client, db, vote_context):
    geo_headers = {
        "x-vercel-ip-country": "PH",
        "x-vercel-ip-country-region": "NCR",
        "x-vercel-ip-city": "Manila",
    }
    url = f"/api/v1/reviews/{vote_context.review.id}/vote"
    headers = {**_auth(vote_context.voter.id), **geo_headers}

    up = client.post(url, headers=headers, json={"vote": "up"})
    assert up.status_code == 200, up.text
    retry = client.post(url, headers=headers, json={"vote": "up"})
    assert retry.status_code == 200, retry.text
    changed = client.post(url, headers=headers, json={"vote": "down"})
    assert changed.status_code == 200, changed.text

    db.expire_all()
    rows = db.execute(
        select(ReviewFirstVoteGeoBucket).where(
            ReviewFirstVoteGeoBucket.review_id == vote_context.review.id
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].first_vote_count == 1
    assert rows[0].country == "PH"


def test_first_vote_geo_with_no_location_is_a_noop_without_a_database():
    assert (
        request_traffic_service.record_first_vote_geo(None, uuid.uuid4(), RequestGeo())
        is False
    )


# ---------------------------------------------------------------------------
# Privacy: the aggregate table's reflected columns carry no voter or IP
# ---------------------------------------------------------------------------

@requires_db
def test_first_vote_geo_bucket_columns_contain_no_voter_identity_or_ip(db):
    from sqlalchemy import MetaData, Table

    engine = db.get_bind()
    reflected = Table(
        "review_first_vote_geo_buckets", MetaData(), autoload_with=engine
    )
    columns = {c.name.lower() for c in reflected.columns}
    for forbidden in ("voter_id", "voter", "ip", "ip_address", "user_id", "reader_ref"):
        assert forbidden not in columns, f"{forbidden} leaked into the aggregate table"
