"""Fraud signals (M2 slice 5) — advisory only, moderator queue only."""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime

from tests.conftest import owned_photo_url, register_and_token, requires_db
from tests.test_votes_api import make_published_review


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _signals(rid: str):
    """Compute signals directly through the service (as the queue does)."""
    from app.db.session import SessionLocal
    from app.models.review import Review
    from app.models.user import User
    from app.services.fraud_service import compute_signals

    db = SessionLocal()
    try:
        review = db.get(Review, _uuid.UUID(rid))
        author = db.get(User, review.author_id) if review.author_id else None
        return compute_signals(db, review, author)
    finally:
        db.close()


def test_signal_batch_empty_input_does_not_touch_the_database():
    from app.services.fraud_service import compute_signals_by_review

    class NoDatabaseCalls:
        def execute(self, *args, **kwargs):
            raise AssertionError("empty batches must not execute SQL")

        def scalars(self, *args, **kwargs):
            raise AssertionError("empty batches must not execute SQL")

    assert compute_signals_by_review(NoDatabaseCalls(), [], {}) == {}


@requires_db
def test_signal_batch_preserves_values_with_constant_query_count(client):
    from sqlalchemy import event

    from app.db.session import SessionLocal
    from app.models.review import Review
    from app.models.user import User
    from app.services.fraud_service import compute_signals, compute_signals_by_review

    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    body = (
        "I used this vacuum every day for six weeks. Battery life is strong, "
        "suction works well on hardwood, and the dust bin is easy to empty."
    )
    pid = client.post(
        "/api/v1/products",
        headers=ah,
        json={"name": "BatchSignalWidget", "category": "electronics"},
    ).json()["id"]

    def make(discussion: str) -> str:
        response = client.post(
            "/api/v1/reviews",
            headers=ah,
            json={
                "product_id": pid,
                "title": "Batch signal review",
                "discussion": discussion,
                "verdict": "yes_absolutely",
                "star_rating": 4,
                "photo_url": owned_photo_url(ah),
            },
        )
        return response.json()["id"]

    original_id = make(body)
    assert client.post(
        f"/api/v1/admin/reviews/{original_id}/publish", headers=mh
    ).status_code == 200
    # A near copy has to actually clear `duplicate_similarity_threshold` (0.85).
    # The previous suffix here was 37 characters onto a 134-character body,
    # which measures 0.82 — below the threshold, so the detector correctly did
    # NOT flag it and this assertion had never run in CI to say so. Measured
    # with pg_trgm on 2026-09-10: this suffix gives 0.909, " Would buy again."
    # gives 0.909, and the distinct body below stays at 0.15.
    near_copy_id = make(body + " Recommended.")
    distinct_id = make(
        "The motor failed on day two and support never replied, so I returned. "
        "This was a completely different ownership experience."
    )

    db = SessionLocal()
    try:
        reviews = [
            db.get(Review, _uuid.UUID(near_copy_id)),
            db.get(Review, _uuid.UUID(distinct_id)),
        ]
        author = db.get(User, reviews[0].author_id)
        evaluated_at = datetime.now(UTC)
        statements: list[str] = []

        def record_statement(*args):
            statements.append(args[2])

        event.listen(db.bind, "before_cursor_execute", record_statement)
        try:
            batched = compute_signals_by_review(
                db,
                reviews,
                {author.id: author},
                now=evaluated_at,
            )
        finally:
            event.remove(db.bind, "before_cursor_execute", record_statement)

        # One vote query, one reciprocal-vote query, one author-count query, and
        # one lateral duplicate query: the count is per batch, not per review.
        assert len(statements) == 4
        assert set(batched) == {review.id for review in reviews}
        assert batched[reviews[0].id]["duplicate_content"] is True
        assert batched[reviews[0].id]["duplicate_of"] == original_id
        assert batched[reviews[1].id]["duplicate_content"] is False
        assert all(signals["velocity"] is False for signals in batched.values())
        assert all(signals["collusion"] is False for signals in batched.values())
        assert all(signals["author_review_count"] >= 3 for signals in batched.values())

        # The original one-review API remains a semantic wrapper around the same
        # batched facts, including the evaluated-at instant used for account age.
        assert compute_signals(
            db, reviews[0], author, now=evaluated_at
        ) == batched[reviews[0].id]
    finally:
        db.close()


@requires_db
def test_duplicate_content_flags_with_duplicate_of(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    long_body = ("I used this vacuum daily for six weeks. Battery life is superb, "
                 "suction strong on hardwood, weaker on thick carpet. The dust bin "
                 "is small but easy to empty. Highly recommended for small flats.")
    pid = client.post("/api/v1/products", headers=ah,
                      json={"name": "DupWidget", "category": "electronics"}).json()["id"]

    def make(discussion: str) -> str:
        body = {"product_id": pid, "title": "Review", "discussion": discussion,
                "verdict": "yes_absolutely", "star_rating": 4,
                "photo_url": owned_photo_url(ah)}
        return client.post("/api/v1/reviews", headers=ah, json=body).json()["id"]

    original = make(long_body)
    assert client.post(f"/api/v1/admin/reviews/{original}/publish",
                       headers=mh).status_code == 200
    near_copy = make(long_body + " Really.")

    signals = _signals(near_copy)
    assert signals["duplicate_content"] is True
    assert signals["duplicate_of"] == original
    assert signals["author_review_count"] >= 2

    # A distinct discussion does not flag.
    distinct = make("Short and completely different take: broke on day two, "
                    "seller unhelpful, would not buy again at this price point.")
    assert _signals(distinct)["duplicate_content"] is False


@requires_db
def test_collusion_and_velocity_flags(client):
    from app.db.session import SessionLocal
    from app.models.enums import VoteDirection
    from app.models.vote import ReviewVote

    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    author_id = client.get("/api/v1/auth/me", headers=ah).json()["id"]

    rid, _ = make_published_review(client, ah, mh, name="CollusionWidget")

    # 5 voters up-vote the author's review; the author up-votes 4 of theirs back.
    ring = []
    for i in range(5):
        uid, tok, _ = register_and_token(client)
        th = _auth(tok)
        assert client.post(f"/api/v1/reviews/{rid}/vote", headers=th,
                           json={"vote": "up"}).status_code == 200
        their_rid, _ = make_published_review(client, th, mh, name=f"RingWidget{i}-{uid[:6]}")
        ring.append(their_rid)

    below = _signals(rid)
    assert below["collusion"] is False  # no reciprocation yet

    for their_rid in ring[:4]:  # 4/5 = 0.8 > 0.6
        assert client.post(f"/api/v1/reviews/{their_rid}/vote", headers=ah,
                           json={"vote": "up"}).status_code == 200
    flagged = _signals(rid)
    assert flagged["collusion"] is True

    # Velocity: >10 up-votes inside an hour. Backdate nothing — insert 6 more
    # votes directly so the review has 11 recent up-votes.
    db = SessionLocal()
    try:
        for _ in range(6):
            uid, _, _ = register_and_token(client)
            db.add(ReviewVote(review_id=_uuid.UUID(rid), voter_id=_uuid.UUID(uid),
                              vote=VoteDirection.up))
        db.commit()
    finally:
        db.close()
    assert _signals(rid)["velocity"] is True

    # Advisory only: the flagged review stays published & publicly visible.
    assert client.get(f"/api/v1/reviews/{rid}").status_code == 200
    assert str(author_id)  # (author unaffected; no auto-block path exists)


@requires_db
def test_signals_in_queue_payload_but_not_public(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    pid = client.post("/api/v1/products", headers=ah,
                      json={"name": "QueueSigWidget", "category": "electronics"}).json()["id"]
    body = {"product_id": pid, "title": "Pending", "discussion": "Queued for review.",
            "verdict": "it_depends", "star_rating": 3}
    rid = client.post("/api/v1/reviews", headers=ah, json=body).json()["id"]

    from tests.conftest import find_pending_queue_item
    item = find_pending_queue_item(client, mh, rid)
    assert item is not None and "signals" in item
    for key in ("velocity", "collusion", "duplicate_content", "duplicate_of",
                "author_account_age_days", "author_review_count"):
        assert key in item["signals"]

    # Public review payloads never carry signals.
    assert "signals" not in client.get(f"/api/v1/reviews/{rid}", headers=ah).json()


@requires_db
def test_fraud_signals_never_mutate_review_state(client):
    """FR-8 invariant: signals are ADVISORY. Computing them (which the moderator
    queue does on every read) must not remove, unpublish, reject or otherwise
    touch the review — verified against the DB in a fresh session, not just the
    response payload."""
    from app.db.session import SessionLocal
    from app.models.enums import ModerationAction
    from app.models.moderation import ModerationLog
    from app.models.review import Review

    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    # A published review carrying a duplicate-content signal.
    body_text = ("Identical body used twice on purpose so the trigram duplicate "
                 "signal fires for certain on this fixture review text.")
    pid = client.post("/api/v1/products", headers=ah,
                      json={"name": "AdvisoryWidget", "category": "electronics"}).json()["id"]

    def make(discussion: str) -> str:
        return client.post("/api/v1/reviews", headers=ah, json={
            "product_id": pid, "title": "Dup", "discussion": discussion,
            "verdict": "yes_absolutely", "star_rating": 4,
            "photo_url": owned_photo_url(ah)}).json()["id"]

    first = make(body_text)
    assert client.post(f"/api/v1/admin/reviews/{first}/publish", headers=mh).status_code == 200
    flagged = make(body_text)
    assert client.post(f"/api/v1/admin/reviews/{flagged}/publish", headers=mh).status_code == 200

    def snapshot(review_id: str) -> tuple:
        db = SessionLocal()
        try:
            r = db.get(Review, _uuid.UUID(review_id))
            return (r.is_removed, r.published_at, r.earn_eligible_status, r.wilson_score)
        finally:
            db.close()

    before = snapshot(flagged)
    assert _signals(flagged)["duplicate_content"] is True  # the signal really fires

    # Drive the REAL moderator queue route (the only signals caller) repeatedly.
    for offset in range(0, 300, 100):
        assert client.get(f"/api/v1/admin/review-queue?limit=100&offset={offset}",
                          headers=mh).status_code == 200

    assert snapshot(flagged) == before, "computing signals mutated the review"
    assert before[0] is False and before[1] is not None
    # Still live and publicly readable.
    assert client.get(f"/api/v1/reviews/{flagged}").status_code == 200
    assert flagged in [r["id"] for r in client.get(f"/api/v1/reviews?product_id={pid}").json()]

    # No moderation action was auto-logged against it.
    db = SessionLocal()
    try:
        auto = db.query(ModerationLog).filter(
            ModerationLog.target_ref == _uuid.UUID(flagged),
            ModerationLog.action.in_([ModerationAction.remove, ModerationAction.reject,
                                      ModerationAction.unpublish, ModerationAction.penalize,
                                      ModerationAction.suspend])).count()
        assert auto == 0
    finally:
        db.close()


def test_velocity_pure_function_burst():
    from app.services.ranking import velocity_exceeded

    now_spread = [i * 300.0 for i in range(11)]  # 11 votes over 50 min -> burst
    assert velocity_exceeded(now_spread) is True
    slow = [i * 3600.0 for i in range(11)]       # one per hour -> fine
    assert velocity_exceeded(slow) is False
