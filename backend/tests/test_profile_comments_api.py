"""A member's own comments — the profile's Comments tab (Figma 5446:6398).

`GET /users/{id}/comments` is the read-side inverse of the thread endpoint: not
"what is under this review" but "what has this member said". A profile is a
public page, so the list has to be safe for a stranger to read — which is what
most of these tests are about.
"""

from __future__ import annotations

from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@requires_db
def test_a_member_with_no_comments_gets_an_empty_list(client):
    user_id, _, _ = register_and_token(client)
    resp = client.get(f"/api/v1/users/{user_id}/comments")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@requires_db
def test_the_list_carries_the_review_the_comment_hangs_off(client):
    """The row draws "<product> - <title>" above the comment body."""
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    commenter_id, commenter_token, _ = register_and_token(client)
    ah, mh, ch = _auth(author_token), _auth(mod_token), _auth(commenter_token)
    rid, _ = make_published_review(client, ah, mh, name="ProfileCommentWidget")

    posted = client.post(f"/api/v1/reviews/{rid}/comments", headers=ch,
                         json={"body": "I'd get the bigger nozzle."})
    assert posted.status_code == 201, posted.text

    rows = client.get(f"/api/v1/users/{commenter_id}/comments").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["body"] == "I'd get the bigger nozzle."
    assert row["review"]["id"] == rid
    assert row["review"]["title"] == "Solid"
    assert row["review"]["product_name"].startswith("ProfileCommentWidget")
    # The reply count on the row is the review's whole thread, not this comment's.
    assert row["review"]["comment_count"] == 1


@requires_db
def test_newest_first(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    commenter_id, commenter_token, _ = register_and_token(client)
    ah, mh, ch = _auth(author_token), _auth(mod_token), _auth(commenter_token)
    rid, _ = make_published_review(client, ah, mh, name="ProfileOrderWidget")

    for body in ("Oldest.", "Middle.", "Newest."):
        assert client.post(f"/api/v1/reviews/{rid}/comments", headers=ch,
                           json={"body": body}).status_code == 201

    rows = client.get(f"/api/v1/users/{commenter_id}/comments").json()
    assert [r["body"] for r in rows] == ["Newest.", "Middle.", "Oldest."]


@requires_db
def test_only_this_member_s_comments_appear(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mine_id, my_token, _ = register_and_token(client)
    _, their_token, _ = register_and_token(client)
    ah, mh = _auth(author_token), _auth(mod_token)
    rid, _ = make_published_review(client, ah, mh, name="ProfileMineWidget")

    client.post(f"/api/v1/reviews/{rid}/comments", headers=_auth(my_token),
                json={"body": "Mine."})
    client.post(f"/api/v1/reviews/{rid}/comments", headers=_auth(their_token),
                json={"body": "Theirs."})

    rows = client.get(f"/api/v1/users/{mine_id}/comments").json()
    assert [r["body"] for r in rows] == ["Mine."]


@requires_db
def test_a_removed_comment_leaves_the_profile(client):
    """The thread keeps a "[removed]" slot; a profile shows nothing at all."""
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    commenter_id, commenter_token, _ = register_and_token(client)
    ah, mh, ch = _auth(author_token), _auth(mod_token), _auth(commenter_token)
    rid, _ = make_published_review(client, ah, mh, name="ProfileRemovedWidget")

    comment = client.post(f"/api/v1/reviews/{rid}/comments", headers=ch,
                          json={"body": "Said in haste."}).json()
    assert client.delete(f"/api/v1/comments/{comment['id']}",
                         headers=ch).status_code == 200

    thread = client.get(f"/api/v1/reviews/{rid}/comments").json()
    assert thread[0]["is_removed"] is True

    assert client.get(f"/api/v1/users/{commenter_id}/comments").json() == []


@requires_db
def test_a_comment_on_an_unpublished_review_is_not_public(client):
    """The author can comment on their own draft; a stranger must not see it."""
    author_id, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)

    published_id, _ = make_published_review(client, ah, mh, name="ProfileGateWidget")
    assert client.post(f"/api/v1/reviews/{published_id}/comments", headers=ah,
                       json={"body": "On the published one."}).status_code == 201

    # An unpublished draft: comments on it are refused outright, so the only way
    # this list could leak one is a bug. Assert the list stays at the one row.
    pid = client.post("/api/v1/products", headers=ah,
                      json={"name": "ProfileDraftWidget", "category": "electronics"}
                      ).json()["id"]
    draft = client.post("/api/v1/reviews", headers=ah, json={
        "product_id": pid, "title": "Draft", "discussion": "Not published yet.",
        "verdict": "it_depends", "star_rating": 3,
    })
    assert draft.status_code == 201, draft.text

    rows = client.get(f"/api/v1/users/{author_id}/comments").json()
    assert [r["review"]["id"] for r in rows] == [published_id]


@requires_db
def test_the_page_size_is_bounded(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    commenter_id, commenter_token, _ = register_and_token(client)
    ah, mh, ch = _auth(author_token), _auth(mod_token), _auth(commenter_token)
    rid, _ = make_published_review(client, ah, mh, name="ProfilePagingWidget")
    for n in range(3):
        client.post(f"/api/v1/reviews/{rid}/comments", headers=ch,
                    json={"body": f"Comment {n}."})

    first = client.get(f"/api/v1/users/{commenter_id}/comments",
                       params={"limit": 2}).json()
    assert len(first) == 2
    second = client.get(f"/api/v1/users/{commenter_id}/comments",
                        params={"limit": 2, "offset": 2}).json()
    assert len(second) == 1
    assert {r["id"] for r in first}.isdisjoint({r["id"] for r in second})

    assert client.get(f"/api/v1/users/{commenter_id}/comments",
                      params={"limit": 0}).status_code == 422
