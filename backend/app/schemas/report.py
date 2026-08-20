"""Content-report schemas (FR-9).

Reports ride on `moderation_logs`, so `ReportOut` is a narrowed projection of a
log row rather than its own table's shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ModerationReason, ModerationTargetType

from app.schemas.urls import web_url_or_none


class ReportCreate(BaseModel):
    reason: ModerationReason
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional context from the reporter.",
    )
    evidence_url: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Optional link backing the report (e.g. the original listing). "
            "Must be http(s) — the moderator queue renders it as a clickable link."
        ),
    )

    @field_validator("evidence_url")
    @classmethod
    def _only_web_urls(cls, value: str | None) -> str | None:
        return web_url_or_none(value, field="Evidence links")


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    log_id: str | None = None
    target_type: ModerationTargetType | None = None
    target_ref: uuid.UUID | None = None
    reporter_id: uuid.UUID | None = None
    reason: ModerationReason | None = None
    notes: str | None = None
    evidence_url: str | None = None
    created_at: datetime
