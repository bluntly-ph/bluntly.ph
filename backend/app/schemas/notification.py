"""Notification schemas (FR-1 1.6)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    body: str | None = None
    #: A same-site path, or null.
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime


class UnreadCount(BaseModel):
    count: int


class MarkedRead(BaseModel):
    #: How many notifications this call marked as read.
    marked: int
