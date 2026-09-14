"""In-app notifications against a real database (FR-1 1.6).

Names carry a per-test suffix: the isolated CI database is cumulative.
"""

from __future__ import annotations

import uuid

from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _product(client, headers: dict) -> str:
    resp = client.post("/api/v1/products", headers=headers,
                       json={"name": f"Notify {uuid.uuid4().hex[:10]}", "category": "electronics"})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _mine(client, headers: dict, **params) -> list[dict]:
    resp = client.get("/api/v1/notifications", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


@requires_db
def test_an_answer_notifies_the_asker_and_only_the_asker(client):
    _, asker, _ = register_and_token(client)
    _, responder, _ = register_and_token(client)
    product_id = _product(client, _auth(asker))
    question = client.post("/api/v1/questions", headers=_auth(asker),
                           json={"product_id": product_id, "body": "Is it loud at night?"}).json()

    assert client.post(f"/api/v1/questions/{question['id']}/answers", headers=_auth(responder),
                       json={"body": "Barely audible on the lowest setting."}).status_code == 201
    # The asker answering their own question is not news to the asker.
    assert client.post(f"/api/v1/questions/{question['id']}/answers", headers=_auth(asker),
                       json={"body": "Update: agreed."}).status_code == 201

    notes = [n for n in _mine(client, _auth(asker)) if n["link"] == f"/questions/{question['id']}"]
    assert [n["kind"] for n in notes] == ["question_answered"]
    assert notes[0]["read_at"] is None
    assert "Barely audible" in (notes[0]["body"] or "")
    assert [n for n in _mine(client, _auth(responder))
            if n["link"] == f"/questions/{question['id']}"] == []


@requires_db
def test_read_state_is_per_account(client):
    _, asker, _ = register_and_token(client)
    _, responder, _ = register_and_token(client)
    product_id = _product(client, _auth(asker))
    question = client.post("/api/v1/questions", headers=_auth(asker),
                           json={"product_id": product_id, "body": "Battery life?"}).json()
    client.post(f"/api/v1/questions/{question['id']}/answers", headers=_auth(responder),
                json={"body": "Two days of normal use."})

    before = client.get("/api/v1/notifications/unread-count", headers=_auth(asker)).json()["count"]
    assert before >= 1
    note = _mine(client, _auth(asker), unread=True)[0]

    # Someone else's notification is not found, not forbidden: its existence
    # is not confirmed to an account it does not belong to.
    other = client.post(f"/api/v1/notifications/{note['id']}/read", headers=_auth(responder))
    assert other.status_code == 404

    read = client.post(f"/api/v1/notifications/{note['id']}/read", headers=_auth(asker))
    assert read.status_code == 200, read.text
    assert read.json()["read_at"] is not None
    after = client.get("/api/v1/notifications/unread-count", headers=_auth(asker)).json()["count"]
    assert after == before - 1

    marked = client.post("/api/v1/notifications/read-all", headers=_auth(asker)).json()["marked"]
    assert marked == after
    assert client.get("/api/v1/notifications/unread-count",
                      headers=_auth(asker)).json()["count"] == 0


@requires_db
def test_a_store_claim_decision_reaches_the_claimant(client):
    _, claimant, _ = register_and_token(client)
    _, moderator, _ = register_and_token(client, role="moderator")
    store = client.post("/api/v1/sellers", headers=_auth(claimant),
                        json={"display_name": f"Notify Store {uuid.uuid4().hex[:10]}",
                              "platform": "shopee"}).json()
    claim = client.post(f"/api/v1/sellers/{store['id']}/claims", headers=_auth(claimant),
                        json={"evidence": "I run it."}).json()
    assert client.post(f"/api/v1/admin/seller-claims/{claim['id']}/decision",
                       headers=_auth(moderator),
                       json={"decision": "approve", "note": "Name matches."}).status_code == 200

    notes = [n for n in _mine(client, _auth(claimant))
             if n["link"] == f"/sellers/{store['id']}/dashboard"]
    assert [n["kind"] for n in notes] == ["seller_claim_approved"]


@requires_db
def test_notifications_need_an_account(client):
    assert client.get("/api/v1/notifications").status_code == 401
    assert client.get("/api/v1/notifications/unread-count").status_code == 401
