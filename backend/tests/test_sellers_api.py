"""The seller flow against a real database (FR-4).

Store names carry a per-test suffix. The isolated CI database is cumulative
across runs, and a fixed store name would collide with a previous run's row and
turn these into tests of leftover data — the failure that has already broken
the ranking test and the export timing once each.
"""

from __future__ import annotations

import uuid

from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _store_name(label: str) -> str:
    return f"{label} Store {uuid.uuid4().hex[:10]}"


def _review(**overrides) -> dict:
    body = {
        "accuracy": True,
        "order_completeness": True,
        "customer_service": 5,
        "packaging_quality": 5,
        "overall_rating": 5,
        "would_recommend": True,
    }
    body.update(overrides)
    return body


def _create_seller(client, headers: dict, name: str) -> dict:
    resp = client.post("/api/v1/sellers", headers=headers,
                       json={"display_name": name, "platform": "shopee"})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


@requires_db
def test_the_same_store_typed_differently_is_one_seller(client):
    _, token, _ = register_and_token(client)
    name = _store_name("Dedup")

    first = _create_seller(client, _auth(token), name)
    again = _create_seller(client, _auth(token), f"  {name.upper()}  ")

    assert again["id"] == first["id"]


@requires_db
def test_an_unrated_store_reports_no_numbers_then_real_ones(client):
    _, token, _ = register_and_token(client)
    seller = _create_seller(client, _auth(token), _store_name("Summary"))

    before = client.get(f"/api/v1/sellers/{seller['id']}").json()
    assert before["summary"]["review_count"] == 0
    assert before["summary"]["overall_average"] is None
    assert before["summary"]["accuracy_rate"] is None

    resp = client.post(f"/api/v1/sellers/{seller['id']}/reviews", headers=_auth(token),
                       json=_review(accuracy=False, overall_rating=4))
    assert resp.status_code == 201, resp.text

    after = client.get(f"/api/v1/sellers/{seller['id']}").json()
    assert after["summary"]["review_count"] == 1
    assert after["summary"]["overall_average"] == 4.0
    assert after["summary"]["accuracy_rate"] == 0.0


@requires_db
def test_one_review_per_reviewer_per_store(client):
    _, token, _ = register_and_token(client)
    seller = _create_seller(client, _auth(token), _store_name("Once"))
    url = f"/api/v1/sellers/{seller['id']}/reviews"

    assert client.post(url, headers=_auth(token), json=_review()).status_code == 201
    second = client.post(url, headers=_auth(token), json=_review(overall_rating=1))
    assert second.status_code == 409
    assert second.json()["code"] == "seller_review_exists"


@requires_db
def test_a_grade_outside_one_to_five_is_refused(client):
    _, token, _ = register_and_token(client)
    seller = _create_seller(client, _auth(token), _store_name("Range"))
    resp = client.post(f"/api/v1/sellers/{seller['id']}/reviews", headers=_auth(token),
                       json=_review(customer_service=6))
    assert resp.status_code == 422


@requires_db
def test_rating_a_store_needs_an_account(client):
    _, token, _ = register_and_token(client)
    seller = _create_seller(client, _auth(token), _store_name("Anon"))
    resp = client.post(f"/api/v1/sellers/{seller['id']}/reviews", json=_review())
    assert resp.status_code == 401


@requires_db
def test_a_claim_waits_for_a_moderator(client):
    _, claimant, _ = register_and_token(client)
    _, other, _ = register_and_token(client)
    _, moderator, _ = register_and_token(client, role="moderator")
    seller = _create_seller(client, _auth(claimant), _store_name("Claim"))
    claims_url = f"/api/v1/sellers/{seller['id']}/claims"

    resp = client.post(claims_url, headers=_auth(claimant),
                       json={"evidence": "Store name matches my order screenshot."})
    assert resp.status_code == 201, resp.text
    claim = resp.json()
    assert claim["status"] == "pending"
    assert client.get(f"/api/v1/sellers/{seller['id']}").json()["claim_status"] != "claimed"

    duplicate = client.post(claims_url, headers=_auth(claimant), json={"evidence": "again"})
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "claim_pending"

    decision_url = f"/api/v1/admin/seller-claims/{claim['id']}/decision"
    self_decided = client.post(decision_url, headers=_auth(claimant),
                               json={"decision": "approve"})
    assert self_decided.status_code == 403

    queue = client.get("/api/v1/admin/seller-claims", headers=_auth(moderator)).json()
    assert any(item["id"] == claim["id"] for item in queue)

    approved = client.post(decision_url, headers=_auth(moderator),
                           json={"decision": "approve", "note": "Cross-checked listing."})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "claimed"
    assert client.get(f"/api/v1/sellers/{seller['id']}").json()["claim_status"] == "claimed"

    late = client.post(claims_url, headers=_auth(other), json={"evidence": "It is mine."})
    assert late.status_code == 409
    assert late.json()["code"] == "seller_already_claimed"


@requires_db
def test_a_rejected_claimant_may_try_again(client):
    _, claimant, _ = register_and_token(client)
    _, moderator, _ = register_and_token(client, role="moderator")
    seller = _create_seller(client, _auth(claimant), _store_name("Retry"))
    claims_url = f"/api/v1/sellers/{seller['id']}/claims"

    first = client.post(claims_url, headers=_auth(claimant), json={"evidence": "thin"}).json()
    rejected = client.post(f"/api/v1/admin/seller-claims/{first['id']}/decision",
                           headers=_auth(moderator),
                           json={"decision": "reject", "note": "Name does not match."})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert client.get(f"/api/v1/sellers/{seller['id']}").json()["claim_status"] != "claimed"

    retry = client.post(claims_url, headers=_auth(claimant),
                        json={"evidence": "Order screenshot attached this time."})
    assert retry.status_code == 201, retry.text


@requires_db
def test_a_store_owner_cannot_rate_their_own_store(client):
    _, owner, _ = register_and_token(client)
    _, moderator, _ = register_and_token(client, role="moderator")
    seller = _create_seller(client, _auth(owner), _store_name("Owner"))

    claim = client.post(f"/api/v1/sellers/{seller['id']}/claims", headers=_auth(owner),
                        json={"evidence": "I run it."}).json()
    client.post(f"/api/v1/admin/seller-claims/{claim['id']}/decision",
                headers=_auth(moderator), json={"decision": "approve"})

    resp = client.post(f"/api/v1/sellers/{seller['id']}/reviews", headers=_auth(owner),
                       json=_review())
    assert resp.status_code == 422
    assert resp.json()["code"] == "self_review"


@requires_db
def test_a_review_carries_its_title_and_its_reviewer(client):
    _, token, _ = register_and_token(client)
    seller = _create_seller(client, _auth(token), _store_name("Content"))
    url = f"/api/v1/sellers/{seller['id']}/reviews"

    resp = client.post(url, headers=_auth(token),
                       json=_review(title="Shipped my package securely",
                                    comment="Bubble wrap on every side."))
    assert resp.status_code == 201, resp.text
    assert resp.json()["title"] == "Shipped my package securely"

    listed = client.get(url).json()
    assert listed[0]["title"] == "Shipped my package securely"
    assert listed[0]["photo_urls"] == []
    assert listed[0]["reviewer"] is not None


@requires_db
def test_a_photo_hosted_anywhere_else_is_refused(client):
    _, token, _ = register_and_token(client)
    seller = _create_seller(client, _auth(token), _store_name("Photo"))
    resp = client.post(f"/api/v1/sellers/{seller['id']}/reviews", headers=_auth(token),
                       json=_review(photo_urls=["https://example.com/not-ours.jpg"]))
    assert resp.status_code == 403
    assert resp.json()["code"] == "photo_not_owned"


@requires_db
def test_search_reports_each_stores_visible_review_count(client):
    _, token, _ = register_and_token(client)
    name = _store_name("Count")
    seller = _create_seller(client, _auth(token), name)
    client.post(f"/api/v1/sellers/{seller['id']}/reviews", headers=_auth(token), json=_review())

    found = client.get("/api/v1/sellers", params={"q": name}).json()
    assert [s["review_count"] for s in found if s["id"] == seller["id"]] == [1]
    assert [s["overall_average"] for s in found if s["id"] == seller["id"]] == [5.0]

    unrated = _create_seller(client, _auth(token), _store_name("Unrated"))
    listed = client.get("/api/v1/sellers", params={"q": unrated["display_name"]}).json()
    assert [(s["review_count"], s["overall_average"]) for s in listed] == [(0, None)]


@requires_db
def test_a_removed_review_leaves_the_page_and_the_numbers(client):
    _, reviewer, _ = register_and_token(client)
    _, moderator, _ = register_and_token(client, role="moderator")
    seller = _create_seller(client, _auth(reviewer), _store_name("Removal"))
    reviews_url = f"/api/v1/sellers/{seller['id']}/reviews"
    created = client.post(reviews_url, headers=_auth(reviewer),
                          json=_review(overall_rating=1)).json()
    removal_url = f"/api/v1/admin/seller-reviews/{created['id']}/removal"

    assert client.post(removal_url, headers=_auth(reviewer), json={}).status_code == 403

    removed = client.post(removal_url, headers=_auth(moderator),
                          json={"note": "Not about this store."})
    assert removed.status_code == 200, removed.text
    assert removed.json()["is_removed"] is True

    assert client.get(reviews_url).json() == []
    detail = client.get(f"/api/v1/sellers/{seller['id']}").json()
    assert detail["summary"]["review_count"] == 0
    assert detail["summary"]["overall_average"] is None
    assert detail["review_count"] == 0

    again = client.post(removal_url, headers=_auth(moderator), json={})
    assert again.status_code == 409
    assert again.json()["code"] == "seller_review_already_removed"


@requires_db
def test_a_moderator_cannot_decide_their_own_claim(client):
    _, moderator, _ = register_and_token(client, role="moderator")
    seller = _create_seller(client, _auth(moderator), _store_name("SelfMod"))
    claim = client.post(f"/api/v1/sellers/{seller['id']}/claims", headers=_auth(moderator),
                        json={"evidence": "I run it and I moderate here."}).json()

    resp = client.post(f"/api/v1/admin/seller-claims/{claim['id']}/decision",
                       headers=_auth(moderator), json={"decision": "approve"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "self_decision"
    assert client.get(f"/api/v1/sellers/{seller['id']}").json()["claim_status"] != "claimed"
