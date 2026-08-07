"""Content-report schemas (FR-9).

Reports ride on `moderation_logs`, so `ReportOut` is a narrowed projection of a
log row rather than its own table's shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ModerationReason, ModerationTargetType

# Anything else — `javascript:`, `data:`, `vbscript:` — becomes script execution
# the moment a moderator clicks the link in the report queue, in THEIR session.
_ALLOWED_URL_SCHEMES = ("http://", "https://")


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
        """Reject non-web schemes.

        This is a reporter-supplied string that a MODERATOR later clicks, so a
        `javascript:` URL here is stored XSS that runs with moderator privileges.
        Validating at the schema boundary means neither the API nor any future
        consumer of `evidence_url` has to remember to sanitize it.
        """
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not value.lower().startswith(_ALLOWED_URL_SCHEMES):
            raise ValueError("Evidence links must start with http:// or https://.")
        return value


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
