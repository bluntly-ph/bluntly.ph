"""Double-submit and post-submit behaviour (BUG-031) — integration.

QA filed this as "cannot verify", not as "broken": double-submit prevention and
post-submit state needed moderator access they did not have. The suspicion was
right. The composer disabled its own button while a request was in flight and
nothing else stopped a second one, so two taps that beat a re-render — or a
retry on a slow connection, or a second tab, or anything posting to the API
directly — produced two identical reviews in the moderation queue, with no way
for their author to remove either.

These tests are the verification QA could not run: the duplicate is refused, a
legitimate second review is not, and the post-submit state is what the
confirmation screen claims it is.
"""

from __future__ import annotations

import uuid

from tests.conftest import owned_photo_url, register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _product(client, headers: dict, name: str) -> str:
    resp = client.post("/api/v1/products", headers=headers,
                       json={"name": f"{name} {uuid.uuid4().hex[:8]}",
                             "category": "electronics"})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _submission(product_id: str, headers: dict, title: str = "Solid") -> dict:
    return {
        "product_id": product_id,
        "title": title,
        "discussion": "Weeks of use and it has held up well.",
        "verdict": "yes_absolutely",
        "star_rating": 4,
        "photo_url": owned_photo_url(headers),
    }


@requires_db
def test_the_same_review_submitted_twice_creates_one(client):
    """The bug in one test: press Publish twice, get one review."""
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    product = _product(client, headers, "DoubleSubmitWidget")
    payload = _submission(product, headers)

    first = client.post("/api/v1/reviews", headers=headers, json=payload)
    assert first.status_code == 201, first.text

    second = client.post("/api/v1/reviews", headers=headers, json=payload)
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "review_already_pending"

    mine = client.get("/api/v1/reviews", headers=headers,
                      params={"product_id": product, "limit": 50})
    assert mine.status_code == 200, mine.text
    ids = {r["id"] for r in mine.json()}
    assert ids == {first.json()["id"]}, "a second review of the product exists"


@requires_db
def test_a_different_title_is_still_a_duplicate_submission(client):
    """The guard is per product, not per payload — a retype is still a retry."""
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    product = _product(client, headers, "RetypeWidget")

    assert client.post("/api/v1/reviews", headers=headers,
                       json=_submission(product, headers, "First go")).status_code == 201
    again = client.post("/api/v1/reviews", headers=headers,
                        json=_submission(product, headers, "Second go"))
    assert again.status_code == 409, again.text


@requires_db
def test_another_reviewer_is_not_blocked_by_yours(client):
    """The rule is per author. Two people reviewing one product is the product."""
    _, mine, _ = register_and_token(client)
    _, theirs, _ = register_and_token(client)
    product = _product(client, _auth(mine), "SharedWidget")

    assert client.post("/api/v1/reviews", headers=_auth(mine),
                       json=_submission(product, _auth(mine))).status_code == 201
    assert client.post("/api/v1/reviews", headers=_auth(theirs),
                       json=_submission(product, _auth(theirs))).status_code == 201


@requires_db
def test_a_second_product_is_not_blocked(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    one = _product(client, headers, "FirstWidget")
    two = _product(client, headers, "SecondWidget")

    assert client.post("/api/v1/reviews", headers=headers,
                       json=_submission(one, headers)).status_code == 201
    assert client.post("/api/v1/reviews", headers=headers,
                       json=_submission(two, headers)).status_code == 201


@requires_db
def test_a_rejected_review_can_be_resubmitted(client):
    """`reject` promises the author may resubmit; the guard must not break that."""
    _, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    headers, mh = _auth(token), _auth(mod_token)
    product = _product(client, headers, "ResubmitWidget")

    first = client.post("/api/v1/reviews", headers=headers,
                        json=_submission(product, headers)).json()["id"]
    rejected = client.post(f"/api/v1/admin/reviews/{first}/reject", headers=mh,
                           json={"reason": "Needs a clearer photo."})
    assert rejected.status_code == 200, rejected.text

    again = client.post("/api/v1/reviews", headers=headers,
                        json=_submission(product, headers, "With a better photo"))
    assert again.status_code == 201, again.text


@requires_db
def test_a_published_review_does_not_block_a_later_one(client):
    """Buying the same thing again a year later is not a double submit."""
    _, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    headers, mh = _auth(token), _auth(mod_token)
    product = _product(client, headers, "SecondPurchaseWidget")

    first = client.post("/api/v1/reviews", headers=headers,
                        json=_submission(product, headers)).json()["id"]
    assert client.post(f"/api/v1/admin/reviews/{first}/publish",
                       headers=mh).status_code == 200

    again = client.post("/api/v1/reviews", headers=headers,
                        json=_submission(product, headers, "Bought it again"))
    assert again.status_code == 201, again.text


@requires_db
def test_post_submit_state_is_what_the_confirmation_claims(client):
    """The other half of BUG-031: where the review goes after Publish.

    The composer's last screen tells the reviewer it is with a moderator. That
    has to be true — hidden from the public, present in the queue, and visible
    to its author.
    """
    _, token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    headers, mh = _auth(token), _auth(mod_token)
    product = _product(client, headers, "PostSubmitWidget")

    created = client.post("/api/v1/reviews", headers=headers,
                          json=_submission(product, headers))
    assert created.status_code == 201, created.text
    review_id = created.json()["id"]

    # Hidden from the public, and from the public feed.
    assert client.get(f"/api/v1/reviews/{review_id}").status_code == 404
    feed = client.get("/api/v1/reviews/feed", params={"limit": 100}).json()
    assert review_id not in [i["review"]["id"] for i in feed]

    # Visible to its author, who was just told where it went.
    assert client.get(f"/api/v1/reviews/{review_id}", headers=headers).status_code == 200

    # And waiting for a moderator, which is what the screen says.
    queue = client.get("/api/v1/admin/review-queue", headers=mh,
                       params={"q": "PostSubmitWidget", "limit": 100}).json()
    assert review_id in [i["review"]["id"] for i in queue["items"]]
