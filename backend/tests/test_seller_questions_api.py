"""Questions asked of a store, against a real database (FR-4, FR-5).

Store names carry a per-test suffix: the isolated CI database is cumulative.
"""

from __future__ import annotations

import uuid

from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _store(client, headers: dict) -> dict:
    resp = client.post("/api/v1/sellers", headers=headers,
                       json={"display_name": f"QA Store {uuid.uuid4().hex[:10]}",
                             "platform": "shopee"})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def _approve_claim(client, owner: dict, moderator: dict, seller_id: str) -> None:
    claim = client.post(f"/api/v1/sellers/{seller_id}/claims", headers=owner,
                        json={"evidence": "I run this store."}).json()
    resp = client.post(f"/api/v1/admin/seller-claims/{claim['id']}/decision",
                       headers=moderator, json={"decision": "approve"})
    assert resp.status_code == 200, resp.text


def _ask(client, headers: dict, seller_id: str, body: str) -> dict:
    resp = client.post("/api/v1/questions", headers=headers,
                       json={"seller_id": seller_id, "body": body})
    assert resp.status_code == 201, resp.text
    return resp.json()


@requires_db
def test_a_store_question_belongs_to_the_store(client):
    _, buyer, _ = register_and_token(client)
    store = _store(client, _auth(buyer))

    q = _ask(client, _auth(buyer), store["id"], "How long do you take to ship?")
    assert q["product_id"] is None
    assert q["seller_id"] == store["id"]
    assert q["seller_name"] == store["display_name"]
    assert q["directed_to"] == "seller"

    listed = client.get("/api/v1/questions", params={"seller_id": store["id"]}).json()
    assert [item["id"] for item in listed] == [q["id"]]


@requires_db
def test_only_the_claimed_owner_answers_as_the_store(client):
    _, owner, _ = register_and_token(client)
    _, buyer, _ = register_and_token(client)
    _, other, _ = register_and_token(client)
    _, moderator, _ = register_and_token(client, role="moderator")
    store = _store(client, _auth(buyer))
    _approve_claim(client, _auth(owner), _auth(moderator), store["id"])
    q = _ask(client, _auth(buyer), store["id"], "Do you ship to Davao?")

    by_store = client.post(f"/api/v1/questions/{q['id']}/answers", headers=_auth(owner),
                           json={"body": "Yes, within three days."})
    assert by_store.status_code == 201, by_store.text
    assert by_store.json()["is_seller_answer"] is True
    assert by_store.json()["seller_name"] == store["display_name"]
    assert by_store.json()["is_first_responder"] is False, (
        "a store answering a question about itself earns no badge")

    by_buyer = client.post(f"/api/v1/questions/{q['id']}/answers", headers=_auth(other),
                           json={"body": "Mine took four days."}).json()
    assert by_buyer["is_seller_answer"] is False
    assert by_buyer["seller_name"] is None

    detail = client.get(f"/api/v1/questions/{q['id']}").json()
    assert detail["seller_name"] == store["display_name"]
    assert sorted(a["is_seller_answer"] for a in detail["answers"]) == [False, True]


@requires_db
def test_a_claimant_still_waiting_answers_as_a_buyer(client):
    _, claimant, _ = register_and_token(client)
    _, buyer, _ = register_and_token(client)
    store = _store(client, _auth(buyer))
    client.post(f"/api/v1/sellers/{store['id']}/claims", headers=_auth(claimant),
                json={"evidence": "It is mine."})
    q = _ask(client, _auth(buyer), store["id"], "Is this store legitimate?")

    answer = client.post(f"/api/v1/questions/{q['id']}/answers", headers=_auth(claimant),
                         json={"body": "Very."}).json()
    assert answer["is_seller_answer"] is False


@requires_db
def test_a_question_needs_one_subject_that_exists(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    assert client.post("/api/v1/questions", headers=headers,
                       json={"body": "About what?"}).status_code == 422

    missing = client.post("/api/v1/questions", headers=headers,
                          json={"seller_id": str(uuid.uuid4()), "body": "Hello?"})
    assert missing.status_code == 404
    assert missing.json()["code"] == "seller_not_found"
