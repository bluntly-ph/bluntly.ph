"""The read-only lists behind the console's Activity Log and Reviewers items.

Both existed as sidebar entries with nothing behind them. These tests pin the
two things that matter about the endpoints that fixed that: they are
moderator-only, and they do not leak identity.

The `target_ref` assertion is deliberate. It is a UUID column being serialized
into a `str` field, and that exact mismatch on the Overview's activity feed
returned a bare 500 in production.
"""

from __future__ import annotations

import uuid

from tests.conftest import register_and_token, requires_db

ACTIVITY = "/api/v1/admin/activity"
REVIEWERS = "/api/v1/admin/reviewers"


# Authorization -------------------------------------------------------------

@requires_db
def test_activity_is_denied_to_anonymous(client):
    assert client.get(ACTIVITY).status_code in (401, 403)


@requires_db
def test_reviewers_is_denied_to_anonymous(client):
    assert client.get(REVIEWERS).status_code in (401, 403)


@requires_db
def test_an_ordinary_reviewer_cannot_read_either(client):
    _, token, _ = register_and_token(client, role="user")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(ACTIVITY, headers=headers).status_code == 403
    assert client.get(REVIEWERS, headers=headers).status_code == 403


# Shape ---------------------------------------------------------------------

@requires_db
def test_a_moderator_reads_the_activity_log(client):
    _, token, _ = register_and_token(client, role="moderator")
    resp = client.get(ACTIVITY, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["rows"], list) and isinstance(body["total"], int)


@requires_db
def test_activity_target_ref_is_a_string_not_a_uuid(client):
    """The regression this whole console correction started from."""
    _, token, _ = register_and_token(client, role="moderator")
    body = client.get(ACTIVITY, headers={"Authorization": f"Bearer {token}"}).json()
    for row in body["rows"]:
        if row["target_ref"] is not None:
            assert isinstance(row["target_ref"], str)
            # And it must still be a real identifier, not a repr.
            uuid.UUID(row["target_ref"])


@requires_db
def test_a_moderator_reads_the_reviewer_list(client):
    _, token, _ = register_and_token(client, role="moderator")
    resp = client.get(REVIEWERS, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1, "the moderator who just registered should be counted"
    assert all("published_reviews" in r for r in body["rows"])


@requires_db
def test_the_reviewer_list_carries_no_identity(client):
    """A moderator managing contributors needs standing and output, not
    identity. No email, no address, no session material."""
    _, token, _ = register_and_token(client, role="moderator")
    raw = client.get(REVIEWERS, headers={"Authorization": f"Bearer {token}"}).text.lower()
    for forbidden in ("email", "@", "password", "ip_address", "session", "token"):
        assert forbidden not in raw, f"{forbidden} leaked into the reviewer list"


@requires_db
def test_paging_is_bounded(client):
    """An unbounded admin list is a way to pull the whole user table in one
    request."""
    _, token, _ = register_and_token(client, role="moderator")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"{REVIEWERS}?limit=500", headers=headers).status_code == 422
    assert client.get(f"{ACTIVITY}?limit=500", headers=headers).status_code == 422
    assert client.get(f"{ACTIVITY}?offset=-1", headers=headers).status_code == 422
