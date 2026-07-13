"""Membership tiers: list, RBAC-gated assignment (integration)."""

from __future__ import annotations

from tests.conftest import register_and_token, requires_db


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@requires_db
def test_list_tiers_after_seed(client):
    from scripts.seed import seed
    seed()  # idempotent
    resp = client.get("/api/v1/membership-tiers")
    assert resp.status_code == 200
    codes = {t["code"] for t in resp.json()}
    assert {"special", "founding", "standard"} <= codes


@requires_db
def test_only_moderator_can_assign_tier(client):
    target_id, _, _ = register_and_token(client)
    _, user_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")

    # Non-moderator is forbidden.
    forbidden = client.patch(f"/api/v1/users/{target_id}/membership-tier",
                             headers=_auth(user_token), json={"membership_tier": "founding"})
    assert forbidden.status_code == 403

    # Moderator can assign.
    ok = client.patch(f"/api/v1/users/{target_id}/membership-tier",
                      headers=_auth(mod_token), json={"membership_tier": "founding"})
    assert ok.status_code == 200
    assert ok.json()["membership_tier"] == "founding"
