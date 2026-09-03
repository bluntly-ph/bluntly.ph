"""Private reading-telemetry ingestion contract.

The browser-facing facade is added separately. This module accepts only
durations and identifiers needed to merge one impression; identity, location,
timestamps, and device class remain server-derived.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AuthError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import get_optional_user
from app.db.session import get_db
from app.models.enums import ReaderKind
from app.services.reading_telemetry_service import (
    CheckpointData,
    ReaderIdentity,
    record_checkpoint,
)

router = APIRouter(prefix="/internal", tags=["internal: reading telemetry"])

INT32_MAX = 2_147_483_647


class ReadingCheckpointIn(BaseModel):
    """The complete and exclusive client-controlled telemetry payload."""

    model_config = ConfigDict(extra="forbid")

    impression_id: UUID4
    review_id: uuid.UUID
    seq: int = Field(strict=True, ge=0, le=INT32_MAX)
    active_ms: int = Field(strict=True, ge=0, le=INT32_MAX)
    body_active_ms: int = Field(strict=True, ge=0, le=INT32_MAX)
    wall_ms: int = Field(strict=True, ge=0, le=INT32_MAX)
    scroll_pct: Literal[0, 25, 50, 75, 100]
    vote_after_ms: int | None = Field(default=None, strict=True, ge=0, le=INT32_MAX)
    report_after_ms: int | None = Field(default=None, strict=True, ge=0, le=INT32_MAX)
    comment_after_ms: int | None = Field(default=None, strict=True, ge=0, le=INT32_MAX)
    share_after_ms: int | None = Field(default=None, strict=True, ge=0, le=INT32_MAX)
    photo_after_ms: int | None = Field(default=None, strict=True, ge=0, le=INT32_MAX)
    outlink_after_ms: int | None = Field(default=None, strict=True, ge=0, le=INT32_MAX)

    @field_validator("scroll_pct", mode="before")
    @classmethod
    def _strict_scroll_integer(cls, value):
        if type(value) is not int:
            raise ValueError("scroll_pct must be an integer milestone")
        return value

    def to_checkpoint_data(self) -> CheckpointData:
        """Discard Pydantic concerns before entering the collection service."""
        return CheckpointData(
            impression_id=self.impression_id,
            review_id=self.review_id,
            seq=self.seq,
            active_ms=self.active_ms,
            body_active_ms=self.body_active_ms,
            wall_ms=self.wall_ms,
            scroll_pct=self.scroll_pct,
            vote_after_ms=self.vote_after_ms,
            report_after_ms=self.report_after_ms,
            comment_after_ms=self.comment_after_ms,
            share_after_ms=self.share_after_ms,
            photo_after_ms=self.photo_after_ms,
            outlink_after_ms=self.outlink_after_ms,
        )


def _require_ingest_key(presented: str | None) -> None:
    configured = settings.telemetry_ingest_key
    supplied = presented or ""
    matches = secrets.compare_digest(configured.encode(), supplied.encode())
    if not configured.strip() or not supplied or not matches:
        raise AuthError("Missing or invalid telemetry ingest key.")


def _reader_identity(
    request: Request,
    db: Session,
    anonymous_header: str | None,
) -> ReaderIdentity:
    """Resolve identity locally without changing the global auth dependency."""
    try:
        user = get_optional_user(request=request, db=db)
    except AuthError:
        user = None

    if user is not None:
        return ReaderIdentity(kind=ReaderKind.user, reader_ref=user.id)

    try:
        anonymous_id = uuid.UUID(anonymous_header) if anonymous_header else None
    except (TypeError, ValueError):
        anonymous_id = None
    if anonymous_id is None:
        raise AuthError("A valid reader identity is required.")
    return ReaderIdentity(kind=ReaderKind.anon, anon_ref=anonymous_id)


@router.post(
    "/reading-telemetry",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Merge one private reading checkpoint",
)
def ingest_reading_checkpoint(
    checkpoint: ReadingCheckpointIn,
    request: Request,
    db: Session = Depends(get_db),
    x_telemetry_key: str | None = Header(default=None, alias="X-Telemetry-Key"),
    x_reader_anon: str | None = Header(default=None, alias="X-Reader-Anon"),
    x_reader_country: str | None = Header(default=None, alias="X-Reader-Country"),
) -> Response:
    """Validate authority and merge collection-only telemetry."""
    _require_ingest_key(x_telemetry_key)
    enforce_rate_limit(
        request,
        "reading_telemetry",
        max_requests=settings.telemetry_rate_limit_max,
        window_seconds=60,
    )
    identity = _reader_identity(request, db, x_reader_anon)
    record_checkpoint(
        db,
        checkpoint.to_checkpoint_data(),
        identity,
        country=x_reader_country,
        user_agent=request.headers.get("user-agent"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
