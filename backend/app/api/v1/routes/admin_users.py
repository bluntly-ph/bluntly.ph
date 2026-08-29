"""Staff user administration: find a person, and appoint moderators.

TWO SCOPES, deliberately different, because they answer to different needs.

  SEARCH — moderator and above.
      Moderators already see every account through GET /admin/reviewers; what
      they cannot do is look anyone up. This adds addressability to a
      population they are already trusted with, which is the whole of the
      owner's stated intent: make users easier for moderators and admins to
      find. Email is returned only to super admins.

  ROLE CHANGE — super admin only.
      Assign or revoke `moderator`, and nothing else.

WHY MODERATORS CANNOT PROMOTE. If a moderator could grant `moderator`, the role
would be self-propagating: one compromised or careless moderator account is
then an unbounded number of them, and no amount of audit logging undoes that.
Appointment stays with the owner.

WHAT CANNOT BE EXPRESSED HERE AT ALL. Super-admin. It is not a MemberRole — it
is a separate column no endpoint writes (see app/models/user.py) — so there is
no request body that grants or revokes it, and no self-elevation or
last-super-admin-standing hazard to guard against. That is by construction, not
by validation.

Authorization is re-derived from the database on every request through the
dependencies below. The UI hides what a caller may not do, but that is
convenience: nothing here trusts it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.security import get_current_user, require_super_admin
from app.db.session import get_db
from app.models.enums import (
    MemberRole,
    ModerationAction,
    ModerationTargetType,
)
from app.models.moderation import ModerationLog
from app.models.user import User
from app.schemas.admin_users import (
    ASSIGNABLE_ROLES,
    RoleChangeIn,
    RoleChangeResult,
    StaffUserPage,
    StaffUserRow,
)
from app.services.staff_directory_service import normalise_staff_ref, search_users

log = get_logger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin: users"])


def require_staff(user: User = Depends(get_current_user)) -> User:
    """Moderator, or super admin.

    Not `require_role("moderator", ...)`: a super admin is identified by a
    column rather than a role, so the two conditions have to be OR-ed here.
    In practice the owner's account is also a moderator, but this must not
    depend on that being true.
    """
    if user.role == MemberRole.moderator or bool(getattr(user, "is_super_admin", False)):
        return user
    raise ForbiddenError("Requires moderator access.", code="role_forbidden")


@router.get("", response_model=StaffUserPage,
            summary="Find an account by staff reference, id, email or name")
def search(
    q: str = Query(default="", max_length=320,
                   description="Staff ref (USR-000123), UUID, exact email, or name"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
) -> StaffUserPage:
    """Lookup, not enumeration.

    An empty query returns nothing. Browsing the population already exists at
    /admin/reviewers; letting this endpoint dump every account as well would
    make one mistyped request a full export.
    """
    rows, total = search_users(db, q, limit=limit, offset=offset)

    # Email is identity, not standing. Moderators get everything they need to
    # recognise an account without it — the existing /admin/reviewers screen
    # makes the same call and says so in its own docstring.
    is_super = bool(getattr(staff, "is_super_admin", False))

    return StaffUserPage(
        total=total,
        resolved_staff_ref=normalise_staff_ref(q),
        can_manage_roles=is_super,
        rows=[
            StaffUserRow(
                id=u.id,
                staff_ref=u.staff_ref,
                display_name=u.display_name,
                username=u.username,
                role=u.role,
                is_suspended=u.is_suspended,
                trust_stage=u.trust_stage,
                created_at=u.created_at,
                email=u.email if is_super else None,
                is_super_admin=bool(u.is_super_admin),
            )
            for u in rows
        ],
    )


@router.patch("/{user_id}/role", response_model=RoleChangeResult,
              summary="Assign or revoke moderator (super admin)")
def set_role(
    user_id: uuid.UUID,
    payload: RoleChangeIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_super_admin),
) -> RoleChangeResult:
    """Move an account between `user` and `moderator`.

    The role change and its audit record are written in ONE transaction. A
    grant that committed without its log would be exactly the situation the log
    exists for — someone holding moderator powers with no record of who gave
    them.
    """
    if payload.role not in ASSIGNABLE_ROLES:
        # Covers `seller` (owned by the existing moderator endpoint) and
        # anything a future enum value might add. Super-admin cannot reach
        # here: it is not a MemberRole.
        raise ForbiddenError(
            f"Only {' and '.join(r.value for r in ASSIGNABLE_ROLES)} may be assigned here.",
            code="role_not_assignable",
            extra={"assignable": [r.value for r in ASSIGNABLE_ROLES]},
        )

    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("User not found.", code="user_not_found")

    # Elevation is out-of-band and constrained to moderator in the database.
    # Letting this endpoint demote the underlying role would violate that
    # invariant even though it would not clear the elevation flag.
    if bool(target.is_super_admin):
        raise ForbiddenError(
            "Super-admin accounts are not managed by this role endpoint.",
            code="role_not_managed_here",
        )

    previous = target.role

    if previous not in ASSIGNABLE_ROLES:
        # A seller's role is managed by the membership endpoint. Silently
        # rewriting it from here would move someone between two different
        # products' worth of semantics.
        raise ForbiddenError(
            f"This account's role is '{previous.value}' and is not managed here.",
            code="role_not_managed_here",
            extra={"actual": previous.value},
        )

    if previous == payload.role:
        # Not an error, and deliberately not an audit entry either: nothing
        # changed, and a log full of no-ops is a log nobody reads.
        return RoleChangeResult(
            id=target.id, staff_ref=target.staff_ref,
            previous_role=previous, role=previous, changed=False,
            detail="already in that role",
        )

    granting = payload.role == MemberRole.moderator
    target.role = payload.role

    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        target_type=ModerationTargetType.user,
        target_ref=target.id,
        moderator_id=actor.id,
        action=ModerationAction.role_grant if granting else ModerationAction.role_revoke,
        notes=f"role {previous.value} -> {payload.role.value}",
        # WHO, WHOM, FROM, TO. No token, no session, no password material, no
        # email — the moderation log is readable by moderators, and this record
        # is about authority rather than identity.
        context={
            "from": previous.value,
            "to": payload.role.value,
            "result": "succeeded",
            "actor_staff_ref": actor.staff_ref,
            "target_staff_ref": target.staff_ref,
        },
    ))
    db.commit()
    db.refresh(target)

    log.info("staff role change",
             extra={"extra_fields": {"action": "role_grant" if granting else "role_revoke",
                                     "from": previous.value, "to": payload.role.value}})

    return RoleChangeResult(
        id=target.id, staff_ref=target.staff_ref,
        previous_role=previous, role=target.role, changed=True,
    )
