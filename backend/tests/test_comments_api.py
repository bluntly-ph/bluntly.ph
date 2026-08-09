"""Review comments (BUG-014) — integration.

Covers what the QA checklist row 24 asks for: reading, posting, ordering,
threading, the empty state, and guest vs logged-in behaviour — plus the
visibility rule that a comment is only as reachable as the review it hangs off.
"""

from __future__ import annotations

from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@requires_db
def test_empty_state_and_guest_read(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    rid, _ = make_published_review(client, ah, mh, name="CommentEmptyWidget")

    # A review with no comments answers 200 + [], not 404 — the page renders an
    # empty state rather than an error.
    resp = client.get(f"/api/v1/reviews/{rid}/comments")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@requires_db
def test_post_read_order_and_guest_cannot_post(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, reader_token, _ = register_and_token(client)
    ah, mh, rh = _auth(author_token), _auth(mod_token), _auth(reader_token)
    rid, _ = make_published_review(client, ah, mh, name="CommentOrderWidget")

    # Guests read but cannot post.
    assert client.post(f"/api/v1/reviews/{rid}/comments",
                       json={"body": "drive-by"}).status_code == 401

    first = client.post(f"/api/v1/reviews/{rid}/comments", headers=rh,
                        json={"body": "First thought."})
    assert first.status_code == 201, first.text
    assert first.json()["body"] == "First thought."
    assert first.json()["author"]["id"] is not None

    second = client.post(f"/api/v1/reviews/{rid}/comments", headers=ah,
                         json={"body": "Author replying to the room."})
    assert second.status_code == 201

    thread = client.get(f"/api/v1/reviews/{rid}/comments").json()
    # Oldest first: a conversation reads top to bottom.
    assert [c["body"] for c in thread] == [
        "First thought.", "Author replying to the room."]
    assert all(c["replies"] == [] for c in thread)


@requires_db
def test_replies_are_one_level_deep(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, reader_token, _ = register_and_token(client)
    ah, mh, rh = _auth(author_token), _auth(mod_token), _auth(reader_token)
    rid, _ = make_published_review(client, ah, mh, name="CommentThreadWidget")

    root = client.post(f"/api/v1/reviews/{rid}/comments", headers=rh,
                       json={"body": "Does it survive a drop?"}).json()
    reply = client.post(f"/api/v1/reviews/{rid}/comments", headers=ah,
                        json={"body": "Mine did.", "parent_id": root["id"]})
    assert reply.status_code == 201, reply.text

    # Replying to a reply is refused rather than silently flattened.
    deeper = client.post(f"/api/v1/reviews/{rid}/comments", headers=rh,
                         json={"body": "and mine", "parent_id": reply.json()["id"]})
    assert deeper.status_code == 409
    assert deeper.json()["code"] == "comment_nesting_too_deep"

    thread = client.get(f"/api/v1/reviews/{rid}/comments").json()
    assert len(thread) == 1
    assert [r["body"] for r in thread[0]["replies"]] == ["Mine did."]


@requires_db
def test_blank_body_rejected(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, reader_token, _ = register_and_token(client)
    ah, mh, rh = _auth(author_token), _auth(mod_token), _auth(reader_token)
    rid, _ = make_published_review(client, ah, mh, name="CommentBlankWidget")

    # Whitespace passes a naive min_length check, so it gets its own case.
    for body in ("", "   ", "\n\t "):
        resp = client.post(f"/api/v1/reviews/{rid}/comments", headers=rh,
                           json={"body": body})
        assert resp.status_code == 422, f"{body!r} was accepted"


@requires_db
def test_unpublished_review_hides_its_thread(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, outsider_token, _ = register_and_token(client)
    ah, mh, oh = _auth(author_token), _auth(mod_token), _auth(outsider_token)
    _, pid = make_published_review(client, ah, mh, name="CommentDraftWidget")

    draft = client.post("/api/v1/reviews", headers=ah, json={
        "product_id": pid, "title": "Draft", "discussion": "Not published yet.",
        "verdict": "it_depends", "star_rating": 3}).json()["id"]

    # The draft's thread is unreachable to guests and outsiders, both read and
    # write — otherwise it enumerates drafts.
    assert client.get(f"/api/v1/reviews/{draft}/comments").status_code == 404
    assert client.get(f"/api/v1/reviews/{draft}/comments",
                      headers=oh).status_code == 404
    assert client.post(f"/api/v1/reviews/{draft}/comments", headers=oh,
                       json={"body": "peek"}).status_code == 404
    # The author still sees their own draft's thread.
    assert client.get(f"/api/v1/reviews/{draft}/comments",
                      headers=ah).status_code == 200


@requires_db
def test_comment_votes_and_self_vote_guard(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, commenter_token, _ = register_and_token(client)
    _, voter_token, _ = register_and_token(client)
    ah, mh = _auth(author_token), _auth(mod_token)
    ch, vh = _auth(commenter_token), _auth(voter_token)
    rid, _ = make_published_review(client, ah, mh, name="CommentVoteWidget")

    cid = client.post(f"/api/v1/reviews/{rid}/comments", headers=ch,
                      json={"body": "Worth the money."}).json()["id"]

    up = client.post(f"/api/v1/comments/{cid}/vote", headers=vh, json={"vote": "up"})
    assert up.status_code == 200, up.text
    assert (up.json()["helpful_votes"], up.json()["unhelpful_votes"]) == (1, 0)

    # Changing direction is an upsert, not a second vote.
    down = client.post(f"/api/v1/comments/{cid}/vote", headers=vh,
                       json={"vote": "down"}).json()
    assert (down["helpful_votes"], down["unhelpful_votes"]) == (0, 1)

    # Voting on your own comment is refused.
    own = client.post(f"/api/v1/comments/{cid}/vote", headers=ch, json={"vote": "up"})
    assert own.status_code == 409
    assert own.json()["code"] == "cannot_vote_own_comment"

    cleared = client.delete(f"/api/v1/comments/{cid}/vote", headers=vh).json()
    assert (cleared["helpful_votes"], cleared["unhelpful_votes"]) == (0, 0)
    # Clearing twice is a 404, matching review votes.
    assert client.delete(f"/api/v1/comments/{cid}/vote", headers=vh).status_code == 404

    # The viewer's own vote comes back on the thread read, so the UI can show the
    # pressed state without a second round trip.
    client.post(f"/api/v1/comments/{cid}/vote", headers=vh, json={"vote": "up"})
    thread = client.get(f"/api/v1/reviews/{rid}/comments", headers=vh).json()
    assert thread[0]["my_vote"] == "up"
    assert client.get(f"/api/v1/reviews/{rid}/comments").json()[0]["my_vote"] is None


@requires_db
def test_removal_keeps_the_thread_shape(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, commenter_token, _ = register_and_token(client)
    _, outsider_token, _ = register_and_token(client)
    ah, mh = _auth(author_token), _auth(mod_token)
    ch, oh = _auth(commenter_token), _auth(outsider_token)
    rid, _ = make_published_review(client, ah, mh, name="CommentRemoveWidget")

    cid = client.post(f"/api/v1/reviews/{rid}/comments", headers=ch,
                      json={"body": "Regrettable take."}).json()["id"]
    client.post(f"/api/v1/reviews/{rid}/comments", headers=ah,
                json={"body": "Replying to it.", "parent_id": cid})

    # Someone else cannot remove it.
    assert client.delete(f"/api/v1/comments/{cid}", headers=oh).status_code == 403

    removed = client.delete(f"/api/v1/comments/{cid}", headers=ch)
    assert removed.status_code == 200, removed.text
    assert removed.json()["is_removed"] is True

    thread = client.get(f"/api/v1/reviews/{rid}/comments").json()
    # The row survives so its reply still has a parent, but the text and the
    # author are gone.
    assert len(thread) == 1
    assert thread[0]["body"] == "[removed]"
    assert thread[0]["author"] is None
    assert [r["body"] for r in thread[0]["replies"]] == ["Replying to it."]


@requires_db
def test_moderator_can_remove_anyones_comment(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, commenter_token, _ = register_and_token(client)
    ah, mh, ch = _auth(author_token), _auth(mod_token), _auth(commenter_token)
    rid, _ = make_published_review(client, ah, mh, name="CommentModWidget")

    cid = client.post(f"/api/v1/reviews/{rid}/comments", headers=ch,
                      json={"body": "Spam link."}).json()["id"]
    assert client.delete(f"/api/v1/comments/{cid}", headers=mh).status_code == 200


@requires_db
def test_reply_parent_must_belong_to_the_same_review(client):
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    _, reader_token, _ = register_and_token(client)
    ah, mh, rh = _auth(author_token), _auth(mod_token), _auth(reader_token)
    first_rid, _ = make_published_review(client, ah, mh, name="CommentGraftA")
    second_rid, _ = make_published_review(client, ah, mh, name="CommentGraftB")

    cid = client.post(f"/api/v1/reviews/{first_rid}/comments", headers=rh,
                      json={"body": "On review A."}).json()["id"]

    # Grafting A's comment onto B's thread must 404, not succeed.
    resp = client.post(f"/api/v1/reviews/{second_rid}/comments", headers=rh,
                       json={"body": "wrong thread", "parent_id": cid})
    assert resp.status_code == 404
    assert resp.json()["code"] == "comment_not_found"
