"""In-app notifications (FR-1 1.6).

`notify` adds a row to the caller's session and never commits: the event that
caused it commits both together, so a notification cannot announce a decision
that was rolled back. Every message's wording lives here, in one place, rather
than being composed at each call site.

Two rules hold for every notification, whoever writes it:

* **the link stays on the site** — only a same-site path is stored; an absolute,
  protocol-relative or backslash URL is dropped and the notification is
  delivered without a link (`safe_internal_link`);
* **the body is an excerpt** — whitespace collapsed, cut on a word boundary at
  `EXCERPT_LIMIT` characters (`excerpt`).
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationOut

EXCERPT_LIMIT = 140

_WHITESPACE = re.compile(r"\s+")


def excerpt(text: str | None, limit: int = EXCERPT_LIMIT) -> str:
    """Whitespace collapsed; cut on a word boundary with an ellipsis when long."""
    if not text:
        return ""
    flat = _WHITESPACE.sub(" ", text).strip()
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut.rstrip() + "…"


def safe_internal_link(link: str | None) -> str | None:
    """A same-site path, or None. Rendered as an href, so nothing else survives."""
    if not link:
        return None
    if not link.startswith("/") or link.startswith("//") or "\\" in link:
        return None
    if any(ch.isspace() or ord(ch) < 32 for ch in link):
        return None
    return link


def notify(db: Session, user_id: uuid.UUID | None, kind: str, title: str, *,
           body: str | None = None, link: str | None = None) -> None:
    """Queue one notification on the caller's session. Does not commit."""
    if user_id is None:
        return
    db.add(Notification(user_id=user_id, kind=kind, title=title[:160],
                        body=excerpt(body) or None, link=safe_internal_link(link)))


# ------------------------------------------------------------ messages

def review_decided(db: Session, review, outcome: str, reason: str | None = None) -> None:
    """A moderator published, rejected or took down the author's review."""
    if outcome == "published":
        notify(db, review.author_id, "review_published", "Your review is live",
               body=review.title, link=f"/reviews/{review.id}")
    elif outcome == "rejected":
        notify(db, review.author_id, "review_rejected", "Your review was not published",
               body=reason or review.title, link="/dashboard/history")
    elif outcome == "unpublished":
        notify(db, review.author_id, "review_unpublished",
               "Your review was taken down for another look",
               body=reason or review.title, link="/dashboard/history")


# ---------------------------------------------------------------- reads

def list_for(db: Session, user: User, *, unread_only: bool, limit: int) -> list[NotificationOut]:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    return [NotificationOut.model_validate(n) for n in db.scalars(stmt).all()]


def unread_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count(Notification.id))
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ) or 0


def mark_read(db: Session, user: User, notification_id: uuid.UUID) -> NotificationOut:
    """Mark one read. Another account's notification is reported as not found,
    so its existence is not confirmed to someone it does not belong to."""
    row = db.get(Notification, notification_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("Notification not found.", code="notification_not_found")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return NotificationOut.model_validate(row)


def mark_all_read(db: Session, user: User) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()
    return result.rowcount or 0
