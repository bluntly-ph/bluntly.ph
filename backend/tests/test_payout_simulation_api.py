"""The simulated GCash / Maya payout preview moves no money (X.4), against a database."""

from __future__ import annotations

from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@requires_db
def test_a_simulation_leaves_the_wallet_and_payouts_untouched(client):
    _, token, _ = register_and_token(client)
    headers = _auth(token)
    wallet_before = client.get("/api/v1/tokens/balance", headers=headers).json()["wallet_balance"]
    payouts_before = client.get("/api/v1/payouts", headers=headers).json()

    for rail in ("gcash", "maya"):
        resp = client.get("/api/v1/payouts/simulate", headers=headers, params={"rail": rail})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["simulated"] is True
        assert body["real_rail"] == "paypal"
        assert body["rail"] == rail

    wallet_after = client.get("/api/v1/tokens/balance", headers=headers).json()["wallet_balance"]
    assert wallet_after == wallet_before
    assert client.get("/api/v1/payouts", headers=headers).json() == payouts_before


@requires_db
def test_only_the_two_simulated_rails_exist(client):
    _, token, _ = register_and_token(client)
    resp = client.get("/api/v1/payouts/simulate", headers=_auth(token),
                      params={"rail": "bank_transfer"})
    assert resp.status_code == 422


@requires_db
def test_the_preview_needs_an_account(client):
    assert client.get("/api/v1/payouts/simulate", params={"rail": "gcash"}).status_code == 401
