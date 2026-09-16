"""moderation_logs (FR-9).

Doubles as the platform AUDIT LOG (deviation/changelog): to honour the 15-table
Data Dictionary we broaden this table's action enum to cover admin/audit actions
(csv_import, payout, honesty_fund_distribution) rather than adding a 16th table.
The target is polymorphic (`target_type` + `target_ref` UUID) since it can point
at reviews, answers, questions, or users.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import (
    ModerationAction,
    ModerationReason,
    ModerationTargetType,
    ReportResolution,
)


class ModerationLog(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "moderation_logs"

    log_id: Mapped[str | None] = mapped_column(String(48), unique=True, index=True)

    target_type: Mapped[ModerationTargetType | None] = mapped_column(
        Enum(ModerationTargetType, name="moderation_target_type")
    )
    # Polymorphic reference (no FK — target table varies). Nullable for pure
    # admin/audit entries (e.g. a CSV import isn't tied to one content row).
    target_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)

    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    moderator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    action: Mapped[ModerationAction] = mapped_column(
        Enum(ModerationAction, name="moderation_action"), nullable=False
    )
    reason: Mapped[ModerationReason | None] = mapped_column(
        Enum(ModerationReason, name="moderation_reason")
    )
    evidence_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    # Free-form structured context (e.g. CSV filename, payout reference, counts).
    context: Mapped[dict | None] = mapped_column(JSONB)

    # --- report resolution (migration 0049) ---------------------------------
    # Only meaningful on rows with `action='report'`: how the moderator closed
    # the report, when, and who. A report with `resolution IS NULL` is still
    # open, which is what the queue reads. The action taken on the content is
    # still audited as its own row by the service that performs it — these three
    # columns say the REPORT was dealt with, not what was done to the content.
    resolution: Mapped[ReportResolution | None] = mapped_column(
        Enum(ReportResolution, name="report_resolution")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
