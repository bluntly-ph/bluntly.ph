"""Trust progression wiring (M2 slice 3) — integration."""

from __future__ import annotations

import math
import uuid as _uuid

from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def ensure_stage_badges() -> None:
    """Tests may run on an unseeded DB; make sure the stage badges exist."""
    from app.db.session import SessionLocal
    from app.models.user import Badge

    codes = [("verified_buyer", "Verified Buyer"),
             ("established_reviewer", "Established Reviewer"),
             ("trusted_reviewer", "Trusted Reviewer"),
             ("community_expert", "Community Expert")]
    db = SessionLocal()
    try:
        for badge_id, name in codes:
            if not db.query(Badge).filter_by(badge_id=badge_id).first():
                db.add(Badge(badge_id=badge_id, name=name))
        db.commit()
    finally:
        db.close()


@requires_db
def test_publish_verified_review_reaches_stage_2_with_badge(client):
    ensure_stage_badges()
    uid, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    trust = client.get(f"/api/v1/users/{uid}/trust").json()
    assert trust["trust_stage"] == 0

    make_published_review(client, ah, mh, name=f"TrustWidget-{uid[:8]}")

    trust = client.get(f"/api/v1/users/{uid}/trust").json()
    assert trust["trust_stage"] == 2
    assert trust["trust_level_name"] == "Verified Buyer"
    assert trust["verified_review_count"] == 1
    badge_ids = [b["badge_id"] for b in trust["badges"]]
    assert badge_ids.count("verified_buyer") == 1

    # Publishing a second review must not duplicate the badge.
    make_published_review(client, ah, mh, name=f"TrustWidget2-{uid[:8]}")
    trust = client.get(f"/api/v1/users/{uid}/trust").json()
    badge_ids = [b["badge_id"] for b in trust["badges"]]
    assert badge_ids.count("verified_buyer") == 1


@requires_db
def test_reputation_score_matches_adr003_formula(client):
    ensure_stage_badges()
    uid, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    rid, _ = make_published_review(client, ah, mh, name=f"RepWidget-{uid[:8]}")

    # One verified review, no votes: 10*log10(1+1) volume points only.
    expected_no_votes = round(min(25.0, 10.0 * math.log10(2)), 2)
    trust = client.get(f"/api/v1/users/{uid}/trust").json()
    assert float(trust["reputation_score"]) == expected_no_votes

    # Three up-votes -> helpfulness 100 -> +60 points.
    for _ in range(3):
        _, tok, _ = register_and_token(client)
        assert client.post(f"/api/v1/reviews/{rid}/vote", headers=_auth(tok),
                           json={"vote": "up"}).status_code == 200
    trust = client.get(f"/api/v1/users/{uid}/trust").json()
    assert float(trust["reputation_score"]) == round(60.0 + expected_no_votes, 2)


@requires_db
def test_trust_endpoint_shape_and_no_manual_stage_set(client):
    uid, token, _ = register_and_token(client)
    trust = client.get(f"/api/v1/users/{uid}/trust").json()
    for key in ("id", "trust_stage", "trust_level_name", "reputation_score",
                "verified_review_count", "helpfulness_ratio", "badges"):
        assert key in trust
    # No API writes trust_stage: users PATCH surface only accepts `role`.
    resp = client.patch(f"/api/v1/users/{uid}/role", headers=_auth(token),
                        json={"role": "seller"})
    assert resp.status_code == 403  # non-moderator
    # Unknown user -> 404.
    assert client.get(f"/api/v1/users/{_uuid.uuid4()}/trust").status_code == 404
