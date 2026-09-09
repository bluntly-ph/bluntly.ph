"""Referral link flow (M2 slice 1) — publication gate, attach/publish/reject/revoke,
attribution redirect, RBAC (integration).

Also the canonical priority-queue contract (Task 2): the prioritized `items`
slice, its `counts`, server filters, and stable policy ordering.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.moderation_priority import PriorityBand, PriorityLane, SlaState
from tests.conftest import owned_photo_url, register_and_token, requires_db

SHOPEE_URL = "https://shopee.ph/product/abc-i.123.456"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_review(client, headers, *, stars: int = 4, photo: bool = True,
                 name: str = "Widget") -> tuple[str, str]:
    pid = client.post("/api/v1/products", headers=headers,
                      json={"name": name, "category": "electronics"}).json()["id"]
    body = {"product_id": pid, "title": "Great", "discussion": "Used it for weeks; solid.",
            "verdict": "yes_absolutely", "star_rating": stars}
    if photo:
        body["photo_url"] = owned_photo_url(headers)
    rid = client.post("/api/v1/reviews", headers=headers, json=body).json()["id"]
    return rid, pid


@requires_db
def test_full_referral_flow(client):
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)

    rid, _ = _make_review(client, ah, stars=4)

    # Hidden from the public list, visible to the author.
    anon_ids = [r["id"] for r in client.get("/api/v1/reviews").json()]
    assert rid not in anon_ids
    own_ids = [r["id"] for r in client.get("/api/v1/reviews", headers=ah).json()]
    assert rid in own_ids
    # Anonymous GET of the unpublished review → 404.
    assert client.get(f"/api/v1/reviews/{rid}").status_code == 404

    # In the moderator queue (paged — dev DBs accumulate pending reviews).
    from tests.conftest import find_pending_queue_item
    assert find_pending_queue_item(client, mh, rid) is not None
    # Non-moderator is forbidden.
    assert client.get("/api/v1/admin/review-queue", headers=ah).status_code == 403

    # Paste link → monetized + published (one action).
    attach = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                         json={"url": SHOPEE_URL, "platform": "shopee"})
    assert attach.status_code == 200, attach.text
    body = attach.json()
    assert body["earn_eligible_status"] == "monetized"
    assert body["published_at"] is not None
    assert body["referral_redirect_url"] == f"/r/{rid}"
    # Raw affiliate URL must NOT be exposed.
    assert "affiliate_link" not in body and SHOPEE_URL not in str(body)

    # Now public.
    assert rid in [r["id"] for r in client.get("/api/v1/reviews").json()]

    # Attribution redirect → 302 to the affiliate URL + a click session row.
    from app.db.session import SessionLocal
    from app.models.session import Session as ClickSession
    resp = client.get(f"/r/{rid}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == SHOPEE_URL
    db = SessionLocal()
    try:
        import uuid as _uuid

        from sqlalchemy import func, select
        n = db.scalar(select(func.count(ClickSession.id)).where(
            ClickSession.review_id == _uuid.UUID(rid)))
        assert n == 1
    finally:
        db.close()

    # Revoke → stays published, drops to approved, redirect 404s.
    rev = client.request("DELETE", f"/api/v1/admin/reviews/{rid}/referral-link",
                         headers=mh, json={"reason": "expired link"})
    assert rev.status_code == 200
    assert rev.json()["earn_eligible_status"] == "approved"
    assert rev.json()["published_at"] is not None       # still live
    assert client.get(f"/r/{rid}", follow_redirects=False).status_code == 404

    # Re-attach works.
    again = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                        json={"url": SHOPEE_URL, "platform": "shopee"})
    assert again.status_code == 200
    assert again.json()["earn_eligible_status"] == "monetized"

    # History shows revoked + active.
    hist = client.get(f"/api/v1/admin/reviews/{rid}/referral-links", headers=mh).json()
    statuses = sorted(link["status"] for link in hist)
    assert statuses == ["active", "revoked"]


@requires_db
def test_low_star_publishes_without_link(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    rid, _ = _make_review(client, _auth(author_token), stars=2)

    # Attaching a link to a <=2* review is refused.
    bad = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                      json={"url": SHOPEE_URL, "platform": "shopee"})
    assert bad.status_code == 409 and bad.json()["code"] == "stars_too_low_for_link"

    # Publish without a link → Honesty Fund, live.
    pub = client.post(f"/api/v1/admin/reviews/{rid}/publish", headers=mh)
    assert pub.status_code == 200
    assert pub.json()["earn_eligible_status"] == "honesty_fund"
    assert pub.json()["published_at"] is not None


@requires_db
def test_reject_then_edit_requeues(client):
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    rid, _ = _make_review(client, ah, stars=5)

    rej = client.post(f"/api/v1/admin/reviews/{rid}/reject", headers=_auth(mod_token),
                      json={"reason": "needs a clearer proof photo"})
    assert rej.status_code == 200
    assert rej.json()["earn_eligible_status"] == "rejected"
    assert rej.json()["published_at"] is None

    edited = client.patch(f"/api/v1/reviews/{rid}", headers=ah,
                          json={"discussion": "Reworded with more detail.", "change_note": "fix"})
    assert edited.json()["earn_eligible_status"] == "pending"  # re-queued


@requires_db
def test_unverified_cannot_be_monetized(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    rid, _ = _make_review(client, _auth(author_token), stars=4, photo=False)  # unverified
    r = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=_auth(mod_token),
                    json={"url": SHOPEE_URL, "platform": "shopee"})
    assert r.status_code == 409 and r.json()["code"] == "review_not_verified"


@requires_db
def test_url_validation_via_attach(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    rid, _ = _make_review(client, _auth(author_token), stars=4)

    # Wrong platform for a valid shopee URL.
    r1 = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                     json={"url": SHOPEE_URL, "platform": "amazon"})
    assert r1.status_code == 422 and r1.json()["code"] == "affiliate_url_invalid"
    # http (not https).
    r2 = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                     json={"url": "http://shopee.ph/x", "platform": "shopee"})
    assert r2.status_code == 422
    # Unrelated domain.
    r3 = client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                     json={"url": "https://evil.example.com/x", "platform": "shopee"})
    assert r3.status_code == 422


@requires_db
def test_admin_routes_require_moderator(client):
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    rid, _ = _make_review(client, ah, stars=4)
    link_body = {"url": SHOPEE_URL, "platform": "shopee"}
    for method, path, body in [
        ("post", f"/api/v1/admin/reviews/{rid}/referral-link", link_body),
        ("post", f"/api/v1/admin/reviews/{rid}/publish", None),
        ("post", f"/api/v1/admin/reviews/{rid}/reject", {"reason": "x"}),
        ("post", f"/api/v1/admin/reviews/{rid}/unpublish", {}),
    ]:
        resp = client.request(method, path, headers=ah, json=body)
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"


@requires_db
def test_edited_since_monetized_flag(client):
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    rid, _ = _make_review(client, ah, stars=4)
    client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                json={"url": SHOPEE_URL, "platform": "shopee"})
    # Author edits after monetization → version bumps past the link's snapshot.
    client.patch(f"/api/v1/reviews/{rid}", headers=ah,
                 json={"title": "Great (revised)", "change_note": "typo"})
    # "Edited since monetized" is a filter on the one canonical queue now —
    # the policy's own factor code — rather than a second response array.
    queue = client.get(
        "/api/v1/admin/review-queue?limit=100&factor=edited_after_monetization",
        headers=mh,
    ).json()
    assert rid in [item["review"]["id"] for item in queue["items"]]
    assert all(item["edited_since_monetized"] for item in queue["items"])


@requires_db
def test_unpublish_returns_the_review_to_the_queue(client):
    """Unpublishing must not strand the review where no moderator can find it.

    `get_queue` selects `earn_eligible_status == pending AND published_at IS
    NULL`. Unpublish used to clear only `published_at`, leaving the status at
    `approved`, so the review vanished from the site and from the queue at the
    same time. Production had two reviews in exactly that state when this was
    found, one of them for eleven days, both put there by a moderator using a
    documented control correctly.
    """
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    rid, _ = _make_review(client, ah, stars=4)

    assert client.post(f"/api/v1/admin/reviews/{rid}/publish",
                       headers=mh).status_code == 200
    unpub = client.post(f"/api/v1/admin/reviews/{rid}/unpublish", headers=mh, json={})
    assert unpub.status_code == 200, unpub.text

    body = unpub.json()
    assert body["published_at"] is None
    assert body["earn_eligible_status"] == "pending"

    from tests.conftest import find_pending_queue_item
    assert find_pending_queue_item(client, mh, rid) is not None, \
        "unpublished review is not in the moderation queue"

    # And the moderator can still act on it: reject requires `pending`-and-down.
    assert client.post(f"/api/v1/admin/reviews/{rid}/reject", headers=mh,
                       json={"reason": "acceptance"}).status_code == 200


@requires_db
def test_unpublish_does_not_leave_a_paying_link(client):
    """A monetized review taken down must stop attributing clicks."""
    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    rid, _ = _make_review(client, ah, stars=4)

    client.post(f"/api/v1/admin/reviews/{rid}/referral-link", headers=mh,
                json={"url": SHOPEE_URL, "platform": "shopee"})
    assert client.get(f"/r/{rid}", follow_redirects=False).status_code == 302

    assert client.post(f"/api/v1/admin/reviews/{rid}/unpublish", headers=mh,
                       json={}).status_code == 200
    assert client.get(f"/r/{rid}", follow_redirects=False).status_code == 404


# --------------------------------------------------------------------------- #
# Canonical priority queue contract (Task 2)
# --------------------------------------------------------------------------- #

_NOW = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)


def _assessed_card(review_id, order_key, *, band, lane, sla, kind="pending",
                   title="card", discussion="body", product_name=None, factors=(),
                   report_count=0):
    """A hand-built ``referral_service._AssessedCard`` for the pure ordering/
    filter/count helpers — no database, no evaluator."""
    from app.models.review import Review
    from app.schemas.referral import (
        QueueItem,
        QueuePriorityAssessment,
        QueuePriorityFactor,
        QueueProduct,
    )
    from app.schemas.review import ReviewOut
    from app.services import referral_service

    priority = QueuePriorityAssessment(
        policy_version="review-priority-v1", lane=lane, score=0, band=band,
        sla_state=sla, due_at=_NOW,
        factors=[QueuePriorityFactor(code=c, observed=True, contribution=5,
                                     explanation=c) for c in factors],
    )
    review = ReviewOut(
        id=review_id, product_id=review_id, title=title, discussion=discussion,
        verdict="it_depends", star_rating=3, verification_status="unverified",
        current_version=1, earn_eligible_status="pending",
        created_at=_NOW, updated_at=_NOW,
    )
    item = QueueItem(
        review=review,
        product=QueueProduct(id=review_id, canonical_name=product_name),
        priority=priority,
    )
    # `review` is the unsaved ORM row the whole-queue aggregation reads columns
    # from; the pure ordering/filter/count helpers below never touch it, so an
    # instance carrying only the id is enough and needs no session.
    return referral_service._AssessedCard(
        review_id=review_id, kind=kind, item=item, order_key=order_key,
        review=Review(id=review_id), report_count=report_count,
    )


def test_assessment_to_queue_schema_maps_every_field():
    from app.models.enums import ModerationReason
    from app.services.moderation_priority import PriorityFacts, evaluate_priority
    from app.services.referral_service import assessment_to_queue_schema

    facts = PriorityFacts(
        queued_at=_NOW - timedelta(hours=6), report_count=4,
        report_reasons=frozenset({ModerationReason.fake_proof}),
        edited_since_monetized=True, velocity=True, collusion=False,
        duplicate_content=False, manually_escalated=False,
    )
    assessment = evaluate_priority(facts, now=_NOW)
    schema = assessment_to_queue_schema(assessment)

    assert schema.policy_version == "review-priority-v1"
    assert schema.lane == assessment.lane
    assert schema.score == assessment.integrity_score
    assert schema.band == assessment.band
    assert schema.sla_state == assessment.sla_state
    assert schema.due_at == assessment.due_at
    assert [f.code for f in schema.factors] == [f.code for f in assessment.factors]
    assert [f.contribution for f in schema.factors] == [
        f.contribution for f in assessment.factors]
    # order_key is server-internal and must not leak onto the wire.
    assert "order_key" not in schema.model_dump()


def test_paginate_cards_orders_by_policy_then_review_id_filters_and_counts():
    import uuid

    from app.services import referral_service as rs

    a, b, c = uuid.UUID(int=1), uuid.UUID(int=2), uuid.UUID(int=3)
    cards = [
        _assessed_card(b, (2, 2, 0), band=PriorityBand.low,
                       lane=PriorityLane.routine, sla=SlaState.on_track),
        # a and c share an order_key -> deterministic tie-break on review id.
        _assessed_card(c, (1, 0, 0), band=PriorityBand.high,
                       lane=PriorityLane.reported, sla=SlaState.overdue,
                       factors=("report_count_4_plus",)),
        _assessed_card(a, (1, 0, 0), band=PriorityBand.high,
                       lane=PriorityLane.reported, sla=SlaState.overdue,
                       factors=("report_count_4_plus",)),
    ]

    page = rs._paginate_cards(cards, rs.QueueQuery(limit=2))
    assert [item.review.id for item in page.items] == [a, c]
    assert page.total == 3
    assert page.next_cursor is None
    assert page.counts.total == 3
    assert page.counts.by_band["high"] == 2
    assert page.counts.by_band["low"] == 1
    assert page.counts.by_lane["reported"] == 2
    assert page.counts.by_sla["overdue"] == 2

    # Stable across repeated calls.
    assert [i.review.id for i in rs._paginate_cards(cards, rs.QueueQuery()).items] == \
           [i.review.id for i in rs._paginate_cards(cards, rs.QueueQuery()).items]

    # Server filters narrow both the page and the counts.
    band_only = rs._paginate_cards(cards, rs.QueueQuery(band=PriorityBand.low))
    assert [i.review.id for i in band_only.items] == [b]
    assert band_only.total == 1 and band_only.counts.by_band["low"] == 1

    factor_only = rs._paginate_cards(
        cards, rs.QueueQuery(factor="report_count_4_plus"))
    assert {i.review.id for i in factor_only.items} == {a, c}

    lane_miss = rs._paginate_cards(cards, rs.QueueQuery(lane=PriorityLane.escalated))
    assert lane_miss.items == [] and lane_miss.total == 0

    sla_only = rs._paginate_cards(cards, rs.QueueQuery(sla=SlaState.on_track))
    assert [i.review.id for i in sla_only.items] == [b]
    assert sla_only.total == 1 and sla_only.counts.by_sla["on_track"] == 1

    second_item = rs._paginate_cards(cards, rs.QueueQuery(limit=1, offset=1))
    assert [i.review.id for i in second_item.items] == [c]
    # Counts and total describe the filtered queue, not the offset window.
    assert second_item.total == 3 and second_item.counts.total == 3


def test_review_queue_serves_one_page_from_one_assessment(monkeypatch):
    """The route evaluates the backlog once and returns exactly that page.

    This test replaces one that asserted the deprecated `pending` /
    `edited_since_monetized` arrays were built from the same assessment as
    `items`. Those arrays are gone: they duplicated the page under a split the
    policy does not use, and two orderings of one backlog is how the console
    came to rank the queue differently from the server. What survives is the
    property that mattered — the unprioritized `get_queue` path is never used
    to answer this endpoint.
    """
    import uuid

    from app.api.v1.routes import admin_referral
    from app.services import referral_service as rs

    review_id = uuid.UUID(int=41)
    card = _assessed_card(
        review_id,
        (3, 2, 0),
        band=PriorityBand.low,
        lane=PriorityLane.routine,
        sla=SlaState.on_track,
    )
    page = rs._paginate_cards([card], rs.QueueQuery())

    calls: list[rs.QueueQuery] = []

    def one_assessment(db, query, *, now=None):
        calls.append(query)
        return page

    monkeypatch.setattr(rs, "get_prioritized_queue", one_assessment)

    def unprioritized_is_a_bug(*args, **kwargs):
        raise AssertionError("the queue endpoint must not fall back to get_queue")

    monkeypatch.setattr(rs, "get_queue", unprioritized_is_a_bug)

    response = admin_referral.review_queue(
        db=object(),
        band=None,
        lane=None,
        sla=None,
        factor=None,
        q=None,
        limit=50,
        offset=0,
    )

    assert len(calls) == 1, "one evaluation per request"
    assert response.items == page.items
    assert response.total == page.total
    assert response.counts == page.counts
    # The split views are gone from the contract, not merely emptied.
    assert not hasattr(response, "pending")
    assert not hasattr(response, "edited_since_monetized")


def _make_pending(client, headers, token, *, verdict="it_depends", stars=3):
    """A pending (unpublished) review whose title carries a unique ``token`` so
    the queue's ``q`` filter can scope a test to exactly its own fixtures."""
    pid = client.post("/api/v1/products", headers=headers,
                      json={"name": f"PrioWidget {token}",
                            "category": "electronics"}).json()["id"]
    body = {"product_id": pid, "title": f"Queued {token}",
            "discussion": f"Priority-contract fixture {token}; weeks of use.",
            "verdict": verdict, "star_rating": stars,
            "photo_url": owned_photo_url(headers)}
    return client.post("/api/v1/reviews", headers=headers, json=body).json()["id"]


def _backdate(review_ids, *, hours):
    import uuid as _uuid

    from app.db.session import SessionLocal
    from app.models.review import Review

    db = SessionLocal()
    try:
        stamp = datetime.now(UTC) - timedelta(hours=hours)
        for rid in review_ids:
            db.get(Review, _uuid.UUID(rid)).created_at = stamp
        db.commit()
    finally:
        db.close()


def _insert_pending_reviews(*, count, token):
    """Insert a large, isolated queue cohort in one transaction.

    Every fixture is anonymous and has its own product, so duplicate-content
    matching cannot turn the ordinary cohort into integrity-lane work.
    """
    import uuid

    from app.db.session import SessionLocal
    from app.models.enums import EarnEligibleStatus, Verdict
    from app.models.product import Product
    from app.models.review import Review

    db = SessionLocal()
    try:
        review_ids = []
        for index in range(count):
            product = Product(
                product_id=f"prd_{uuid.uuid4().hex[:10]}",
                canonical_name=f"Boundary product {token} {index}",
                category="electronics",
            )
            db.add(product)
            db.flush()
            review = Review(
                review_id=f"rev_{uuid.uuid4().hex[:10]}",
                product_id=product.id,
                author_id=None,
                title=f"Boundary queue {token} {index}",
                discussion=f"Independent boundary fixture {index} for {token}.",
                verdict=Verdict.it_depends,
                star_rating=3,
                published_at=None,
                earn_eligible_status=EarnEligibleStatus.pending,
            )
            db.add(review)
            db.flush()
            review_ids.append(str(review.id))
        db.commit()
        return review_ids
    finally:
        db.close()


@requires_db
def test_review_queue_priority_pagination_and_band_filter(client):
    """The pinned Task 2 example, scoped with ``q`` so it is stable on the
    persistent test database."""
    import uuid

    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    moderator_headers = _auth(mod_token)

    token = uuid.uuid4().hex[:12]
    rids = [_make_pending(client, ah, token) for _ in range(3)]
    # Two days in the queue on a 24h routine SLA -> overdue -> band "high".
    _backdate(rids, hours=48)

    response = client.get(
        f"/api/v1/admin/review-queue?limit=2&band=high&q={token}",
        headers=moderator_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert all(item["priority"]["band"] == "high" for item in body["items"])
    assert body["items"][0]["priority"]["policy_version"] == "review-priority-v1"
    assert body["counts"]["by_band"]["high"] == 3
    assert body["counts"]["total"] == 3
    # Each card still says which timestamp stood in for the queue-entry time.
    assert all(item["queue_time_basis"] == "review_created_at"
               for item in body["items"])


@requires_db
def test_review_queue_high_priority_new_review_leads_page_one(client):
    """A high-priority review created AFTER a batch of ordinary ones still leads
    page one — the old created-at ordering would have buried it last."""
    import uuid

    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)

    token = uuid.uuid4().hex[:12]
    ordinary = _insert_pending_reviews(count=51, token=token)

    # Created last, so it is newest by created_at. Published, reported four times
    # for fake proof, then unpublished -> back to pending WITH the report facts.
    hot = _make_pending(client, ah, token, stars=4)
    assert client.post(f"/api/v1/admin/reviews/{hot}/publish", headers=mh).status_code == 200
    for _ in range(4):
        _, reporter_token, _ = register_and_token(client)
        assert client.post(f"/api/v1/reviews/{hot}/report", headers=_auth(reporter_token),
                           json={"reason": "fake_proof"}).status_code == 201
    assert client.post(f"/api/v1/admin/reviews/{hot}/unpublish", headers=mh,
                       json={}).status_code == 200

    from app.db.session import SessionLocal
    from app.services.referral_service import get_queue

    db = SessionLocal()
    try:
        old_first_50, _ = get_queue(db, limit=50)
        assert hot not in {str(review.id) for review in old_first_50}
    finally:
        db.close()

    response = client.get(
        f"/api/v1/admin/review-queue?q={token}&limit=10", headers=mh
    )
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [item["review"]["id"] for item in body["items"]]
    assert body["total"] == 52
    assert len(ids) == 10
    assert ids[0] == hot
    assert set(ids[1:]).issubset(set(ordinary))
    assert body["items"][0]["priority"]["band"] == "high"
    assert body["items"][0]["priority"]["lane"] == "reported"
    assert any(f["code"] == "report_count_4_plus"
               for f in body["items"][0]["priority"]["factors"])

    # Recency alone would have placed it dead last.
    from app.models.review import Review

    db = SessionLocal()
    try:
        hot_created_at = db.get(Review, uuid.UUID(hot)).created_at
        ordinary_created_ats = [
            db.get(Review, uuid.UUID(review_id)).created_at for review_id in ordinary
        ]
    finally:
        db.close()
    assert all(created_at < hot_created_at for created_at in ordinary_created_ats)


@requires_db
def test_review_queue_ties_are_stable_across_repeated_calls(client):
    import uuid as _uuid

    from app.db.session import SessionLocal
    from app.models.review import Review

    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)

    token = _uuid.uuid4().hex[:12]
    rids = [_make_pending(client, ah, token) for _ in range(4)]

    # Identical queued_at -> identical order_key -> the only differentiator is the
    # review UUID appended to the sort key.
    db = SessionLocal()
    try:
        stamp = datetime.now(UTC) - timedelta(hours=1)
        for rid in rids:
            db.get(Review, _uuid.UUID(rid)).created_at = stamp
        db.commit()
    finally:
        db.close()

    first = client.get(f"/api/v1/admin/review-queue?q={token}&limit=10",
                       headers=mh).json()["items"]
    second = client.get(f"/api/v1/admin/review-queue?q={token}&limit=10",
                        headers=mh).json()["items"]
    order_one = [i["review"]["id"] for i in first]
    order_two = [i["review"]["id"] for i in second]
    assert order_one == order_two
    assert order_one == sorted(order_one, key=_uuid.UUID)
    factor_sets = [
        tuple(factor["code"] for factor in item["priority"]["factors"])
        for item in first
    ]
    assert all(factor_sets), "the tie regression must exercise non-empty assessments"
    assert len(set(factor_sets)) == 1


@requires_db
def test_review_queue_mixes_pending_and_edited_sources_with_truthful_time_basis(client):
    import uuid

    _, author_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)

    token = uuid.uuid4().hex[:12]
    pending_id = _make_pending(client, ah, token)
    edited_id = _make_pending(client, ah, token, stars=4)
    attach = client.post(
        f"/api/v1/admin/reviews/{edited_id}/referral-link",
        headers=mh,
        json={"url": SHOPEE_URL, "platform": "shopee"},
    )
    assert attach.status_code == 200, attach.text
    edit = client.patch(
        f"/api/v1/reviews/{edited_id}",
        headers=ah,
        json={"title": f"Edited queue {token}", "change_note": "clarified"},
    )
    assert edit.status_code == 200, edit.text

    response = client.get(
        f"/api/v1/admin/review-queue?q={token}&limit=10", headers=mh
    )
    assert response.status_code == 200, response.text
    body = response.json()
    by_id = {item["review"]["id"]: item for item in body["items"]}
    assert body["total"] == 2
    assert set(by_id) == {pending_id, edited_id}
    assert by_id[pending_id]["queue_time_basis"] == "review_created_at"
    assert by_id[pending_id]["edited_since_monetized"] is False
    assert by_id[edited_id]["queue_time_basis"] == "review_updated_at"
    assert by_id[edited_id]["edited_since_monetized"] is True
    assert by_id[edited_id]["priority"]["lane"] == "integrity"
    assert any(
        factor["code"] == "edited_after_monetization"
        for factor in by_id[edited_id]["priority"]["factors"]
    )


@requires_db
def test_review_queue_invalid_filters_return_422(client):
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    for qs in ("band=urgent", "lane=nowhere", "sla=late", "limit=0", "limit=500",
               "offset=-1"):
        resp = client.get(f"/api/v1/admin/review-queue?{qs}", headers=mh)
        assert resp.status_code == 422, f"{qs} -> {resp.status_code}"


@requires_db
def test_review_queue_non_moderator_forbidden(client):
    _, author_token, _ = register_and_token(client)
    resp = client.get("/api/v1/admin/review-queue?band=high&limit=2",
                      headers=_auth(author_token))
    assert resp.status_code == 403


def test_assess_open_queue_aggregates_the_whole_backlog(monkeypatch):
    """`assess_open_queue` is the Overview's only view of the queue, and every
    DB-backed test of it skips on a machine without PostgreSQL. This pins the
    derivation itself: totals from the same cards, and `reported` meaning at
    least one report — NOT the reported lane, which a manual escalation outranks.
    """
    import uuid as _uuid

    from app.services import referral_service
    from app.services.moderation_priority import PriorityBand, PriorityLane, SlaState

    high = _uuid.uuid4()
    normal = _uuid.uuid4()
    low = _uuid.uuid4()
    cards = [
        _assessed_card(high, (0, 0, 0, _NOW, _NOW), band=PriorityBand.high,
                       lane=PriorityLane.escalated, sla=SlaState.overdue,
                       report_count=2),
        _assessed_card(normal, (1, 1, 0, _NOW, _NOW), band=PriorityBand.normal,
                       lane=PriorityLane.reported, sla=SlaState.approaching,
                       report_count=1),
        _assessed_card(low, (3, 2, 0, _NOW, _NOW), band=PriorityBand.low,
                       lane=PriorityLane.routine, sla=SlaState.on_track),
    ]
    monkeypatch.setattr(referral_service, "_all_queue_candidates", lambda db: [])
    monkeypatch.setattr(
        referral_service, "_build_assessed_cards", lambda db, reviews, now=None: cards
    )

    summary = referral_service.assess_open_queue(object())

    assert summary.total == 3
    assert summary.counts.by_band == {"high": 1, "normal": 1, "low": 1}
    assert summary.counts.by_sla == {"overdue": 1, "approaching": 1, "on_track": 1}
    assert summary.counts.by_lane["escalated"] == 1
    assert summary.high_priority == 1
    assert summary.approaching == 1
    assert summary.overdue == 1
    # The escalated card carries reports even though its lane says "escalated".
    assert summary.reported_review_ids == {high, normal}
    assert [r.id for r in summary.reviews] == [high, normal, low]
