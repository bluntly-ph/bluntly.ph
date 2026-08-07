"""Community content reports (FR-9).

Reports are stored as `moderation_logs` rows with `action=report` and the
reporting user in `reporter_id`. That table is deliberately the single audit
surface (see models/moderation.py — the 15-table Data Dictionary constraint), so
a report is an audit entry a moderator later resolves rather than a row in a
separate reports table.

Two rules keep the queue meaningful:

- You cannot report your own content. Self-reports carry no signal and would let
  an author manufacture "contested" status on their own review.
- One open report per (reporter, target). Re-submitting is idempotent and returns
  the existing report rather than letting one user inflate the count on a review
  they dislike.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import ModerationAction, ModerationReason, ModerationTargetType
from app.models.moderation import ModerationLog


def _existing_report(
    db: Session,
    reporter_id: uuid.UUID,
    target_type: ModerationTargetType,
    target_ref: uuid.UUID,
) -> ModerationLog | None:
    return db.scalars(
        select(ModerationLog).where(
            ModerationLog.action == ModerationAction.report,
            ModerationLog.reporter_id == reporter_id,
            ModerationLog.target_type == target_type,
            ModerationLog.target_ref == target_ref,
        )
    ).first()


def file_report(
    db: Session,
    *,
    reporter_id: uuid.UUID,
    author_id: uuid.UUID | None,
    target_type: ModerationTargetType,
    target_ref: uuid.UUID,
    reason: ModerationReason,
    notes: str | None = None,
    evidence_url: str | None = None,
) -> tuple[ModerationLog, bool]:
    """File a report. Returns (log, created) — `created` is False on a repeat.

    The caller supplies `author_id` so the self-report check happens here rather
    than being re-implemented per content type.
    """
    if author_id is not None and author_id == reporter_id:
        raise AppError(
            "You cannot report your own content.",
            code="self_report",
            status_code=422,
            title="Invalid report",
        )

    existing = _existing_report(db, reporter_id, target_type, target_ref)
    if existing is not None:
        return existing, False

    log = ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        target_type=target_type,
        target_ref=target_ref,
        reporter_id=reporter_id,
        action=ModerationAction.report,
        reason=reason,
        notes=notes,
        evidence_url=evidence_url,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log, True


def list_reports(
    db: Session,
    *,
    target_type: ModerationTargetType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ModerationLog]:
    """The moderator queue of filed reports, newest first."""
    stmt = select(ModerationLog).where(ModerationLog.action == ModerationAction.report)
    if target_type is not None:
        stmt = stmt.where(ModerationLog.target_type == target_type)
    stmt = stmt.order_by(ModerationLog.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def report_counts(
    db: Session, target_type: ModerationTargetType, target_refs: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """How many distinct reports each target has, for badging the moderator queue."""
    if not target_refs:
        return {}
    from sqlalchemy import func

    rows = db.execute(
        select(ModerationLog.target_ref, func.count(ModerationLog.id))
        .where(
            ModerationLog.action == ModerationAction.report,
            ModerationLog.target_type == target_type,
            ModerationLog.target_ref.in_(target_refs),
        )
        .group_by(ModerationLog.target_ref)
    ).all()
    return {row[0]: row[1] for row in rows}
