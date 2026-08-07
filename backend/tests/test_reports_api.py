"""Community content reports (FR-9) — integration.

Reports are `moderation_logs` rows with `action=report`; these tests pin the
guards that keep the moderator queue meaningful (no self-reports, no duplicate
inflation) and the moderator-only visibility of the queue itself.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models.enums import ModerationAction, ModerationTargetType
from app.models.moderation import ModerationLog
from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@requires_db
def test_report_guards(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, reporter_token, _ = register_and_token(client)
    ah, mh, rh = _auth(author_token), _auth(mod_token), _auth(reporter_token)

    rid, pid = make_published_review(client, ah, mh, name="ReportWidget")

    # Anonymous report -> 401.
    resp = client.post(f"/api/v1/reviews/{rid}/report", json={"reason": "spam"})
    assert resp.status_code == 401

    # Self-report -> 422 with the pinned code.
    resp = client.post(f"/api/v1/reviews/{rid}/report", headers=ah,
                       json={"reason": "spam"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "self_report"

    # A reason outside the enum -> 422 (validation, not a free-text field).
    resp = client.post(f"/api/v1/reviews/{rid}/report", headers=rh,
                       json={"reason": "i_just_dont_like_it"})
    assert resp.status_code == 422

    # Report on an unpublished draft -> 404 (drafts stay unenumerable).
    body = {"product_id": pid, "title": "Draft", "discussion": "Unpublished draft.",
            "verdict": "it_depends", "star_rating": 3}
    draft = client.post("/api/v1/reviews", headers=ah, json=body).json()["id"]
    resp = client.post(f"/api/v1/reviews/{draft}/report", headers=rh,
                       json={"reason": "spam"})
    assert resp.status_code == 404


@requires_db
def test_report_is_recorded_and_idempotent(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, reporter_token, _ = register_and_token(client)
    ah, mh, rh = _auth(author_token), _auth(mod_token), _auth(reporter_token)

    rid, _ = make_published_review(client, ah, mh, name="IdempotentWidget")

    resp = client.post(f"/api/v1/reviews/{rid}/report", headers=rh,
                       json={"reason": "fake_proof", "notes": "Receipt looks reused."})
    assert resp.status_code == 201, resp.text
    first = resp.json()
    assert first["reason"] == "fake_proof"
    assert first["notes"] == "Receipt looks reused."
    assert first["target_type"] == "review"
    assert first["target_ref"] == rid

    # Re-reporting the same review returns the ORIGINAL row, not a second one:
    # one reporter must not be able to inflate a review's report count.
    resp = client.post(f"/api/v1/reviews/{rid}/report", headers=rh,
                       json={"reason": "spam"})
    assert resp.status_code == 201
    assert resp.json()["id"] == first["id"]
    assert resp.json()["reason"] == "fake_proof"  # unchanged by the repeat

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        # Scoped to THIS review — the suite shares a database, so a global count
        # would be coupled to every other test that files a report.
        count = db.scalar(
            select(func.count(ModerationLog.id)).where(
                ModerationLog.action == ModerationAction.report,
                ModerationLog.target_type == ModerationTargetType.review,
                ModerationLog.target_ref == uuid.UUID(rid),
            )
        )
    finally:
        db.close()
    assert count == 1


@requires_db
def test_evidence_url_rejects_script_schemes(client):
    """A reporter must not be able to hand a moderator a click-to-execute link.

    `evidence_url` is rendered as an anchor in the moderator queue, so a
    `javascript:` URL here would be stored XSS running with moderator
    privileges.
    """
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, reporter_token, _ = register_and_token(client)
    ah, mh, rh = _auth(author_token), _auth(mod_token), _auth(reporter_token)

    rid, _ = make_published_review(client, ah, mh, name="EvidenceWidget")

    for hostile in (
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        "vbscript:msgbox(1)",
        "/etc/passwd",
    ):
        resp = client.post(f"/api/v1/reviews/{rid}/report", headers=rh,
                           json={"reason": "spam", "evidence_url": hostile})
        assert resp.status_code == 422, f"{hostile!r} was accepted: {resp.text}"

    # A genuine web link still works.
    resp = client.post(f"/api/v1/reviews/{rid}/report", headers=rh,
                       json={"reason": "spam",
                             "evidence_url": "https://shopee.ph/product/123"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["evidence_url"] == "https://shopee.ph/product/123"


@requires_db
def test_report_queue_is_moderator_only(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, reporter_token, _ = register_and_token(client)
    ah, mh, rh = _auth(author_token), _auth(mod_token), _auth(reporter_token)

    rid, _ = make_published_review(client, ah, mh, name="QueueWidget")
    client.post(f"/api/v1/reviews/{rid}/report", headers=rh,
                json={"reason": "harassment"})

    # Anonymous and ordinary users can't read the queue.
    assert client.get("/api/v1/admin/reports").status_code == 401
    assert client.get("/api/v1/admin/reports", headers=rh).status_code == 403

    resp = client.get("/api/v1/admin/reports", headers=mh)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    mine = [i for i in items if i["target"] and i["target"]["id"] == rid]
    assert len(mine) == 1
    assert mine[0]["report"]["reason"] == "harassment"
    assert mine[0]["target_report_count"] == 1
    assert mine[0]["reporter"] is not None


@requires_db
def test_report_count_aggregates_distinct_reporters(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    rid, _ = make_published_review(client, ah, mh, name="PileOnWidget")

    for _ in range(3):
        _, token, _ = register_and_token(client)
        resp = client.post(f"/api/v1/reviews/{rid}/report", headers=_auth(token),
                           json={"reason": "plagiarized"})
        assert resp.status_code == 201, resp.text

    resp = client.get("/api/v1/admin/reports", headers=mh)
    mine = [i for i in resp.json()["items"] if i["target"] and i["target"]["id"] == rid]
    assert len(mine) == 3
    # Three separate people flagged the same review — the queue must show that.
    assert all(i["target_report_count"] == 3 for i in mine)
