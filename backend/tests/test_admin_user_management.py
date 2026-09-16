"""Access matrix and audit contract for staff user management."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.models.enums import MemberRole, ModerationAction
from app.models.moderation import ModerationLog
from app.models.user import User
from tests.conftest import make_user, requires_db

pytestmark = requires_db


def _headers(user: User) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"
    }


@pytest.fixture
def accounts(db):
    target_name = f"Directory {uuid.uuid4().hex[:10]}"
    normal = make_user(
        db, display_name=target_name, username=f"target_{uuid.uuid4().hex[:8]}")
    moderator = make_user(db, role=MemberRole.moderator, display_name="Moderator")
    # The root owner is the configured email AND the super-admin column (owner
    # rule, 2026-09-16). A second elevated account is created alongside it,
    # because "another super admin cannot do this" is the new guarantee.
    #
    # The CONFIGURED email is pointed at a fresh address for the duration of the
    # fixture rather than the account being created at the real one. `users.email`
    # is unique and the CI database is shared and long-lived, so a literal
    # bluntly.ph@gmail.com row survives any run that dies before its teardown —
    # and then every test in this file fails on a UniqueViolation in its fixture,
    # which is what happened. The rule under test is "the configured address",
    # not one particular string, so this tests exactly what it did before and
    # cannot collide with a previous run.
    owner_email = f"root_owner_{uuid.uuid4().hex[:12]}@example.com"
    previous_root_owner = settings.root_owner_email
    settings.root_owner_email = owner_email
    super_admin = make_user(
        db,
        role=MemberRole.moderator,
        is_super_admin=True,
        display_name="Owner",
        email=owner_email,
    )
    other_super = make_user(
        db,
        role=MemberRole.moderator,
        is_super_admin=True,
        display_name="Second elevated account",
    )
    db.commit()
    ids = [normal.id, moderator.id, super_admin.id, other_super.id]
    try:
        yield normal, moderator, super_admin, other_super
    finally:
        settings.root_owner_email = previous_root_owner
        db.rollback()
        db.query(ModerationLog).filter(
            (ModerationLog.target_ref.in_(ids))
            | (ModerationLog.moderator_id.in_(ids))
        ).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        db.info.get("created_users", []).clear()


def test_normal_user_cannot_search_or_change_roles(client, accounts):
    normal, moderator, _, _other_super = accounts
    response = client.get(
        f"/api/v1/admin/users?q={moderator.staff_ref}", headers=_headers(normal))
    assert response.status_code == 403
    assert moderator.staff_ref not in response.text

    response = client.patch(
        f"/api/v1/admin/users/{moderator.id}/role",
        json={"role": "user"},
        headers=_headers(normal),
    )
    assert response.status_code == 403


def test_moderator_can_resolve_staff_ref_without_email_but_cannot_change_role(
    client, accounts
):
    normal, moderator, _, _other_super = accounts
    response = client.get(
        f"/api/v1/admin/users?q={normal.staff_ref.lower()}",
        headers=_headers(moderator),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["can_manage_roles"] is False
    assert body["resolved_staff_ref"] == normal.staff_ref
    assert body["rows"][0]["staff_ref"] == normal.staff_ref
    assert body["rows"][0]["email"] is None

    response = client.patch(
        f"/api/v1/admin/users/{normal.id}/role",
        json={"role": "moderator"},
        headers=_headers(moderator),
    )
    assert response.status_code == 403


def test_legacy_membership_endpoint_cannot_revoke_moderator(client, accounts):
    _, moderator, super_admin, _other_super = accounts
    response = client.patch(
        f"/api/v1/users/{moderator.id}/role",
        json={"role": "user"},
        headers=_headers(super_admin),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "role_not_managed_here"


def test_super_admin_searches_and_grants_then_revokes_with_audit(
    client, db, accounts
):
    normal, _, super_admin, _other_super = accounts

    for query in (normal.staff_ref, str(normal.id), normal.email, normal.display_name):
        response = client.get(
            f"/api/v1/admin/users?q={query}", headers=_headers(super_admin))
        assert response.status_code == 200
        body = response.json()
        assert body["can_manage_roles"] is True
        assert body["rows"][0]["id"] == str(normal.id)
        assert body["rows"][0]["email"] == normal.email

    grant = client.patch(
        f"/api/v1/admin/users/{normal.id}/role",
        json={"role": "moderator"},
        headers=_headers(super_admin),
    )
    assert grant.status_code == 200
    assert grant.json()["role"] == "moderator"
    assert grant.json()["previous_role"] == "user"

    db.expire_all()
    grant_log = db.query(ModerationLog).filter(
        ModerationLog.target_ref == normal.id,
        ModerationLog.action == ModerationAction.role_grant,
    ).one()
    assert grant_log.moderator_id == super_admin.id
    assert grant_log.context == {
        "from": "user",
        "to": "moderator",
        "result": "succeeded",
        "actor_staff_ref": super_admin.staff_ref,
        "target_staff_ref": normal.staff_ref,
    }

    revoke = client.patch(
        f"/api/v1/admin/users/{normal.id}/role",
        json={"role": "user"},
        headers=_headers(super_admin),
    )
    assert revoke.status_code == 200
    assert revoke.json()["role"] == "user"

    db.expire_all()
    assert db.query(ModerationLog).filter(
        ModerationLog.target_ref == normal.id,
        ModerationLog.action == ModerationAction.role_revoke,
    ).count() == 1


def test_super_admin_surface_cannot_assign_seller_or_super_admin(client, accounts):
    normal, _, super_admin, _other_super = accounts
    response = client.patch(
        f"/api/v1/admin/users/{normal.id}/role",
        json={"role": "seller"},
        headers=_headers(super_admin),
    )
    assert response.status_code == 403

    response = client.patch(
        f"/api/v1/admin/users/{normal.id}/role",
        json={"role": "super_admin"},
        headers=_headers(super_admin),
    )
    assert response.status_code == 422

    response = client.patch(
        f"/api/v1/admin/users/{super_admin.id}/role",
        json={"role": "user"},
        headers=_headers(super_admin),
    )
    assert response.status_code == 403


def test_public_and_self_endpoints_do_not_emit_staff_reference(client, accounts):
    normal, _, _, _other_super = accounts
    me = client.get("/api/v1/auth/me", headers=_headers(normal))
    assert me.status_code == 200
    assert "staff_ref" not in me.json()
    assert normal.staff_ref not in me.text

    trust = client.get(f"/api/v1/users/{normal.id}/trust")
    assert trust.status_code == 200
    assert "staff_ref" not in trust.json()
    assert normal.staff_ref not in trust.text


# --- the root-owner rule (owner requirement, 2026-09-16) ---------------------


@requires_db
def test_only_the_root_owner_can_appoint_a_moderator(client, accounts):
    """A second super admin is elevated, and still cannot widen the circle."""
    normal, _moderator, root_owner, other_super = accounts

    refused = client.patch(
        f"/api/v1/admin/users/{normal.id}/role",
        headers=_headers(other_super),
        json={"role": "moderator"},
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "root_owner_required"

    allowed = client.patch(
        f"/api/v1/admin/users/{normal.id}/role",
        headers=_headers(root_owner),
        json={"role": "moderator"},
    )
    assert allowed.status_code == 200, allowed.text
    body = allowed.json()
    assert body["changed"] is True
    assert body["role"] == "moderator"
    assert body["previous_role"] == "user"


@requires_db
def test_only_the_root_owner_can_revoke_a_moderator(client, accounts):
    _normal, moderator, root_owner, other_super = accounts

    refused = client.patch(
        f"/api/v1/admin/users/{moderator.id}/role",
        headers=_headers(other_super),
        json={"role": "user"},
    )
    assert refused.status_code == 403, refused.text

    allowed = client.patch(
        f"/api/v1/admin/users/{moderator.id}/role",
        headers=_headers(root_owner),
        json={"role": "user"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["role"] == "user"


@requires_db
def test_a_moderator_cannot_appoint_anyone(client, accounts):
    normal, moderator, _root_owner, _other = accounts
    refused = client.patch(
        f"/api/v1/admin/users/{normal.id}/role",
        headers=_headers(moderator),
        json={"role": "moderator"},
    )
    assert refused.status_code == 403, refused.text


@requires_db
def test_the_console_only_offers_the_controls_to_the_root_owner(client, accounts):
    """`can_manage_roles` is what the console reads; it must track the guard."""
    normal, moderator, root_owner, other_super = accounts
    for account, expected in ((root_owner, True), (other_super, False), (moderator, False)):
        page = client.get(
            "/api/v1/admin/users", headers=_headers(account), params={"q": normal.display_name}
        )
        assert page.status_code == 200, page.text
        assert page.json()["can_manage_roles"] is expected


@requires_db
def test_every_role_change_is_written_to_the_audit_log(client, accounts, db):
    """Actor, target, old role, new role, timestamp — in one transaction."""
    normal, _moderator, root_owner, _other = accounts
    before = db.query(ModerationLog).count()

    done = client.patch(
        f"/api/v1/admin/users/{normal.id}/role",
        headers=_headers(root_owner),
        json={"role": "moderator"},
    )
    assert done.status_code == 200, done.text

    entry = (
        db.query(ModerationLog)
        .filter(ModerationLog.target_ref == normal.id)
        .order_by(ModerationLog.created_at.desc())
        .first()
    )
    assert db.query(ModerationLog).count() == before + 1
    assert entry is not None
    assert entry.moderator_id == root_owner.id
    assert entry.context["from"] == "user"
    assert entry.context["to"] == "moderator"
    assert entry.created_at is not None
