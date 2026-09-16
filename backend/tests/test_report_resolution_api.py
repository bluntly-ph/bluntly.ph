"""Resolving a community report (owner §30, 2026-09-16) — integration.

Before this, the report queue was inspection only: a moderator could read a
report and had no way to answer it, so every report ever filed stayed in the
queue for ever. These tests pin the four outcomes, what each one does to the
content, and the guards around them.
"""

from __future__ import annotations

import uuid

from app.models.enums import ModerationAction, ModerationTargetType, ReportResolution
from app.models.moderation import ModerationLog
from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _file_report(client, review_id: str, reporter_headers: dict) -> str:
    filed = client.post(f"/api/v1/reviews/{review_id}/report",
                        headers=reporter_headers, json={"reason": "spam"})
    assert filed.status_code in (200, 201), filed.text
    return filed.json()["id"]


def _cast(client):
    """An author, a moderator, a reporter and a published review."""
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, reporter_token, _ = register_and_token(client)
    ah, mh, rh = _auth(author_token), _auth(mod_token), _auth(reporter_token)
    rid, _ = make_published_review(client, ah, mh, name="ResolveWidget")
    return ah, mh, rh, rid


@requires_db
def test_an_open_report_is_in_the_queue_and_a_resolved_one_is_not(client):
    _ah, mh, rh, rid = _cast(client)
    report_id = _file_report(client, rid, rh)

    queue = client.get("/api/v1/admin/reports", headers=mh).json()
    assert report_id in [i["report"]["id"] for i in queue["items"]]

    done = client.post(f"/api/v1/admin/reports/{report_id}/decision", headers=mh,
                       json={"resolution": "dismissed", "notes": "Read it; it stands."})
    assert done.status_code == 200, done.text
    assert done.json()["report"]["resolution"] == "dismissed"

    after = client.get("/api/v1/admin/reports", headers=mh).json()
    assert report_id not in [i["report"]["id"] for i in after["items"]]

    # ...but it is not gone. The audit surface keeps it.
    resolved = client.get("/api/v1/admin/reports", headers=mh,
                          params={"status": "resolved"}).json()
    assert report_id in [i["report"]["id"] for i in resolved["items"]]


@requires_db
def test_dismissing_leaves_the_review_published(client):
    _ah, mh, rh, rid = _cast(client)
    report_id = _file_report(client, rid, rh)

    client.post(f"/api/v1/admin/reports/{report_id}/decision", headers=mh,
                json={"resolution": "dismissed"})

    review = client.get(f"/api/v1/reviews/{rid}")
    assert review.status_code == 200
    assert review.json()["published_at"] is not None


@requires_db
def test_removing_takes_the_review_down_and_restoring_puts_it_back(client):
    ah, mh, rh, rid = _cast(client)
    _, second_reporter_token, _ = register_and_token(client)

    # BOTH reports are filed while the review is still public. A reader cannot
    # report a review they can no longer see — `/reviews/{id}/report` resolves
    # the review through the same publication gate as everything else and
    # answers 404 — so the second one has to exist before the first is acted on.
    first = _file_report(client, rid, rh)
    second = _file_report(client, rid, _auth(second_reporter_token))

    removed = client.post(f"/api/v1/admin/reports/{first}/decision", headers=mh,
                          json={"resolution": "content_removed",
                                "notes": "Fabricated proof."})
    assert removed.status_code == 200, removed.text
    assert removed.json()["target"]["is_published"] is False

    # Gone from the public read path, and back in the moderation queue rather
    # than stranded — that is what `unpublish` guarantees and this must inherit.
    assert client.get(f"/api/v1/reviews/{rid}").status_code == 404
    # Scoped by the fixture's product name, not by the id: `q` is a free-text
    # match on the title, the body and the product, and a UUID matches none of
    # them. An unscoped page of 100 is a slice of a backlog that grows with
    # every CI run.
    queue = client.get("/api/v1/admin/review-queue", headers=mh,
                       params={"q": "ResolveWidget", "limit": 100}).json()
    assert rid in [i["review"]["id"] for i in queue["items"]]

    restored = client.post(f"/api/v1/admin/reports/{second}/decision", headers=mh,
                           json={"resolution": "content_restored"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["target"]["is_published"] is True
    assert client.get(f"/api/v1/reviews/{rid}").status_code == 200


@requires_db
def test_every_resolution_is_audited_with_the_actor_and_the_report(client, db):
    _ah, mh, rh, rid = _cast(client)
    report_id = _file_report(client, rid, rh)
    before = db.query(ModerationLog).filter(
        ModerationLog.action == ModerationAction.approve).count()

    client.post(f"/api/v1/admin/reports/{report_id}/decision", headers=mh,
                json={"resolution": "dismissed", "notes": "No violation."})

    entries = db.query(ModerationLog).filter(
        ModerationLog.action == ModerationAction.approve).all()
    assert len(entries) == before + 1
    entry = max(entries, key=lambda e: e.created_at)
    assert entry.context["report_id"] == report_id
    assert entry.context["resolution"] == "dismissed"
    assert entry.notes == "No violation."
    assert entry.moderator_id is not None

    # And the report row itself carries who closed it and when.
    report = db.get(ModerationLog, entry.context["report_id"])
    assert report.resolution is ReportResolution.dismissed
    assert report.resolved_at is not None
    assert report.resolved_by == entry.moderator_id


@requires_db
def test_a_report_cannot_be_resolved_twice(client):
    _ah, mh, rh, rid = _cast(client)
    report_id = _file_report(client, rid, rh)

    assert client.post(f"/api/v1/admin/reports/{report_id}/decision", headers=mh,
                       json={"resolution": "dismissed"}).status_code == 200
    again = client.post(f"/api/v1/admin/reports/{report_id}/decision", headers=mh,
                        json={"resolution": "escalated"})
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "report_already_resolved"


@requires_db
def test_only_a_moderator_can_resolve(client):
    _ah, mh, rh, rid = _cast(client)
    report_id = _file_report(client, rid, rh)

    assert client.post(f"/api/v1/admin/reports/{report_id}/decision",
                       json={"resolution": "dismissed"}).status_code == 401
    refused = client.post(f"/api/v1/admin/reports/{report_id}/decision", headers=rh,
                          json={"resolution": "dismissed"})
    assert refused.status_code == 403, refused.text


@requires_db
def test_the_reporter_may_report_again_once_their_report_was_answered(client):
    """The duplicate guard is "one OPEN report", not "one ever"."""
    _ah, mh, rh, rid = _cast(client)
    first = _file_report(client, rid, rh)

    # While it is open, re-reporting is idempotent — the same row comes back.
    again = client.post(f"/api/v1/reviews/{rid}/report", headers=rh,
                        json={"reason": "spam"})
    assert again.json()["id"] == first

    client.post(f"/api/v1/admin/reports/{first}/decision", headers=mh,
                json={"resolution": "dismissed"})

    reopened = client.post(f"/api/v1/reviews/{rid}/report", headers=rh,
                           json={"reason": "spam"})
    assert reopened.json()["id"] != first, "a closed report must not silence the reader"


@requires_db
def test_a_target_with_no_publish_state_can_only_be_dismissed_or_escalated(client, db):
    """Questions, answers, sellers and users are reportable; none is publishable.

    There is no route that files a report against one of those yet — only
    reviews have `POST /reviews/{id}/report` — so the row is written directly.
    The guard is on the resolution path, and that is what is under test.
    """
    _, mod_token, _ = register_and_token(client, role="moderator")
    reporter_id, _, _ = register_and_token(client)
    mh = _auth(mod_token)

    filed = ModerationLog(
        target_type=ModerationTargetType.question,
        target_ref=uuid.uuid4(),
        reporter_id=uuid.UUID(reporter_id),
        action=ModerationAction.report,
    )
    db.add(filed)
    db.commit()
    report_id = str(filed.id)

    refused = client.post(f"/api/v1/admin/reports/{report_id}/decision", headers=mh,
                          json={"resolution": "content_removed"})
    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "report_target_not_actionable"

    # The report is still open — a refused content action must not close it.
    db.refresh(filed)
    assert filed.resolution is None

    escalated = client.post(f"/api/v1/admin/reports/{report_id}/decision", headers=mh,
                            json={"resolution": "escalated"})
    assert escalated.status_code == 200, escalated.text
    assert escalated.json()["report"]["resolution"] == "escalated"


@requires_db
def test_the_report_target_type_survives_resolution(client):
    _ah, mh, rh, rid = _cast(client)
    report_id = _file_report(client, rid, rh)
    done = client.post(f"/api/v1/admin/reports/{report_id}/decision", headers=mh,
                       json={"resolution": "dismissed"}).json()
    assert done["report"]["target_type"] == ModerationTargetType.review.value
    assert done["report"]["target_ref"] == rid
