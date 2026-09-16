"""The public reviewer profile, resolvable by handle (BUG-030) — integration.

QA filed this as an S1 blocker: `/u/{username}` answered "Reviewer not found"
for every real reviewer. Two causes, and both are covered here:

  * the page resolved its subject through the review feed's `author_id`, which
    takes a UUID, so a handle could never match;
  * a reviewer with no PUBLISHED review has no feed row, so an account that
    plainly exists answered "not found".

The third thing these tests are for is what the endpoint must NOT return. A
public profile is a page a stranger opens, and the spec is explicit that
earnings stay private to the reviewer and to moderators.
"""

from __future__ import annotations

import uuid

from app.models.user import User
from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _set_username(user_id: str, handle: str) -> None:
    """Give the account a known handle; registration allocates a generated one."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        user = db.get(User, uuid.UUID(user_id))
        user.username = handle
        db.commit()
    finally:
        db.close()


@requires_db
def test_a_reviewer_resolves_by_their_handle(client):
    """The bug in one test: /u/{username} has to find a real reviewer."""
    user_id, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    handle = f"ciel_{uuid.uuid4().hex[:8]}"
    _set_username(user_id, handle)
    make_published_review(client, _auth(token), _auth(mod_token), name="PublicProfileWidget")

    resp = client.get(f"/api/v1/users/public/{handle}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == user_id
    assert body["username"] == handle
    assert body["review_count"] == 1


@requires_db
def test_the_same_reviewer_resolves_by_id(client):
    """The site links by id; both spellings have to reach the same page."""
    user_id, _, _ = register_and_token(client)
    handle = f"mleux_{uuid.uuid4().hex[:8]}"
    _set_username(user_id, handle)

    by_handle = client.get(f"/api/v1/users/public/{handle}").json()
    by_id = client.get(f"/api/v1/users/public/{user_id}").json()
    assert by_handle == by_id


@requires_db
def test_a_capitalised_handle_still_resolves(client):
    """Usernames are stored lowercased; a link from someone's notes is not."""
    user_id, _, _ = register_and_token(client)
    handle = f"mixedcase_{uuid.uuid4().hex[:8]}"
    _set_username(user_id, handle)

    resp = client.get(f"/api/v1/users/public/{handle.upper()}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == user_id


@requires_db
def test_a_reviewer_with_nothing_published_is_not_a_404(client):
    """The other half of BUG-030. Existing and silent are different answers."""
    user_id, _, _ = register_and_token(client)
    handle = f"quiet_{uuid.uuid4().hex[:8]}"
    _set_username(user_id, handle)

    resp = client.get(f"/api/v1/users/public/{handle}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["review_count"] == 0
    assert resp.json()["id"] == user_id


@requires_db
def test_an_unknown_handle_is_a_real_404(client):
    for handle in [f"nobody_{uuid.uuid4().hex[:10]}", str(uuid.uuid4())]:
        resp = client.get(f"/api/v1/users/public/{handle}")
        assert resp.status_code == 404, f"{handle}: {resp.text}"
        assert resp.json()["code"] == "user_not_found"


@requires_db
def test_a_malformed_handle_is_a_404_not_a_500(client):
    """Whatever someone types after /u/ reaches this endpoint."""
    for handle in ["..", "%20", "a", "-", "null", "undefined"]:
        resp = client.get(f"/api/v1/users/public/{handle}")
        assert resp.status_code in (404, 422), f"{handle}: {resp.status_code}"


@requires_db
def test_the_public_profile_leaks_nothing_private(client):
    """Earnings, email, role and staff flags stay off a page strangers open."""
    user_id, _, email = register_and_token(client)
    handle = f"private_{uuid.uuid4().hex[:8]}"
    _set_username(user_id, handle)

    body = client.get(f"/api/v1/users/public/{handle}").json()

    forbidden = {
        "email", "role", "is_super_admin", "password_hash", "wallet_balance",
        "lifetime_earnings", "available_balance", "membership_tier", "interests",
        "phone", "last_login_at",
    }
    assert forbidden.isdisjoint(body.keys()), (
        f"the public profile carries private fields: {forbidden & set(body)}"
    )
    # Not just absent by key — the email must not appear anywhere in the body.
    assert email not in str(body)


@requires_db
def test_it_needs_no_session(client):
    """A stranger is the intended caller; a token must not be required."""
    user_id, _, _ = register_and_token(client)
    handle = f"anon_{uuid.uuid4().hex[:8]}"
    _set_username(user_id, handle)

    assert client.get(f"/api/v1/users/public/{handle}").status_code == 200


@requires_db
def test_the_trust_figures_are_the_reviewer_s_own(client):
    """The header draws these; borrowing another account's would be worse than none."""
    user_id, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    handle = f"trusted_{uuid.uuid4().hex[:8]}"
    _set_username(user_id, handle)
    make_published_review(client, _auth(token), _auth(mod_token), name="PublicTrustWidget")

    body = client.get(f"/api/v1/users/public/{handle}").json()
    trust = client.get(f"/api/v1/users/{user_id}/trust").json()

    assert body["trust_stage"] == trust["trust_stage"]
    assert body["trust_level_name"] == trust["trust_level_name"]
    assert body["verified_review_count"] == trust["verified_review_count"]
