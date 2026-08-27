"""Read-only lists the admin console's navigation needs.

Two sidebar items in the approved design — Activity Log and Reviewers — had no
API behind them, so they were rendered as dead controls. These are the smallest
endpoints that make them work: both are read-only, both are moderator-gated by
the router dependency, and neither adds a new concept to the domain.

Nothing here writes. Actions on reviews and payouts already have their own
routes and are not duplicated.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.moderation import ModerationLog
from app.models.review import Review
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin: console"],
                   dependencies=[Depends(require_role("moderator"))])


class ActivityRow(BaseModel):
    id: uuid.UUID
    action: str
    actor: str | None
    target_type: str | None
    #: Always a string. `moderation_logs.target_ref` is a UUID column and this
    #: is a str field; the two disagreeing is what took the Overview down.
    target_ref: str | None
    at: datetime


class ActivityPage(BaseModel):
    rows: list[ActivityRow]
    total: int


@router.get("/activity", response_model=ActivityPage,
            summary="The moderation audit log, newest first")
def activity_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ActivityPage:
    """Every recorded moderator action, including the ones the Overview's
    five-item feed deliberately leaves out."""
    total = int(db.scalar(select(func.count()).select_from(ModerationLog)) or 0)
    rows = db.execute(
        select(ModerationLog, User.display_name, User.username)
        .outerjoin(User, User.id == ModerationLog.moderator_id)
        .order_by(ModerationLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ActivityPage(
        total=total,
        rows=[
            ActivityRow(
                id=log.id,
                action=log.action.value if hasattr(log.action, "value") else str(log.action),
                actor=display or username,
                target_type=(log.target_type.value
                             if getattr(log.target_type, "value", None) else
                             (str(log.target_type) if log.target_type else None)),
                target_ref=str(log.target_ref) if log.target_ref is not None else None,
                at=log.created_at,
            )
            for log, display, username in rows
        ],
    )


class ReviewerRow(BaseModel):
    id: uuid.UUID
    username: str | None
    display_name: str | None
    role: str
    trust_stage: int
    reputation_score: str
    published_reviews: int
    joined: datetime


class ReviewerPage(BaseModel):
    rows: list[ReviewerRow]
    total: int


@router.get("/reviewers", response_model=ReviewerPage,
            summary="Contributors, with trust stage and published counts")
def reviewers(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ReviewerPage:
    """Deliberately carries no email, no address and no session data: a
    moderator managing contributors needs standing and output, not identity."""
    published = (
        select(Review.author_id, func.count().label("n"))
        .where(Review.published_at.is_not(None), Review.is_removed.is_(False))
        .group_by(Review.author_id)
        .subquery()
    )
    total = int(db.scalar(select(func.count()).select_from(User)) or 0)
    rows = db.execute(
        select(User, func.coalesce(published.c.n, 0))
        .outerjoin(published, published.c.author_id == User.id)
        .order_by(func.coalesce(published.c.n, 0).desc(), User.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ReviewerPage(
        total=total,
        rows=[
            ReviewerRow(
                id=u.id,
                username=u.username,
                display_name=u.display_name,
                role=u.role.value if hasattr(u.role, "value") else str(u.role),
                trust_stage=u.trust_stage,
                reputation_score=str(u.reputation_score),
                published_reviews=int(n or 0),
                joined=u.created_at,
            )
            for u, n in rows
        ],
    )
