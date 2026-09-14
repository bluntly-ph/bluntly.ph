"""In-app notification routes (FR-1 1.6). Every route is the caller's own.

The static paths (`/unread-count`, `/read-all`) are declared before the
parameterised one so neither is ever parsed as a notification id.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import MarkedRead, NotificationOut, UnreadCount
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut], summary="Your notifications, newest first")
def list_notifications(db: Session = Depends(get_db),
                       user: User = Depends(get_current_user),
                       unread: bool = False,
                       limit: int = Query(30, ge=1, le=100)) -> list[NotificationOut]:
    return notification_service.list_for(db, user, unread_only=unread, limit=limit)


@router.get("/unread-count", response_model=UnreadCount, summary="How many are unread")
def unread_count(db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> UnreadCount:
    return UnreadCount(count=notification_service.unread_count(db, user))


@router.post("/read-all", response_model=MarkedRead, summary="Mark every notification read")
def read_all(db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> MarkedRead:
    return MarkedRead(marked=notification_service.mark_all_read(db, user))


@router.post("/{notification_id}/read", response_model=NotificationOut,
             summary="Mark one notification read")
def read_one(notification_id: uuid.UUID, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> NotificationOut:
    return notification_service.mark_read(db, user, notification_id)
