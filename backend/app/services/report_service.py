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
from collections.abc import Collection, Iterator
from datetime import UTC, datetime
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.models.enums import (
    ModerationAction,
    ModerationReason,
    ModerationTargetType,
    ReportResolution,
)
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
            # OPEN, which is what the rule above always said and what the table
            # could not express until reports could be closed (migration 0049).
            # A reader whose report was dealt with may report the same target
            # again if it goes wrong again; a reader whose report is still
            # waiting may not file it twice.
            ModerationLog.resolution.is_(None),
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
    status: str = "open",
    limit: int = 50,
    offset: int = 0,
) -> list[ModerationLog]:
    """The moderator queue of filed reports, newest first.

    `status` is "open" (the default), "resolved" or "all". Open is the default
    because the queue is a to-do list: before reports could be closed it showed
    every report ever filed, so work already done came back round for ever.
    """
    stmt = select(ModerationLog).where(ModerationLog.action == ModerationAction.report)
    if target_type is not None:
        stmt = stmt.where(ModerationLog.target_type == target_type)
    if status == "open":
        stmt = stmt.where(ModerationLog.resolution.is_(None))
    elif status == "resolved":
        stmt = stmt.where(ModerationLog.resolution.is_not(None))
    stmt = stmt.order_by(ModerationLog.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def get_report_or_404(db: Session, report_id: uuid.UUID) -> ModerationLog:
    """One filed report. A log row that is not a report is not found."""
    log = db.get(ModerationLog, report_id)
    if log is None or log.action != ModerationAction.report:
        raise NotFoundError("Report not found.", code="report_not_found")
    return log


def resolve_report(
    db: Session,
    report: ModerationLog,
    *,
    moderator_id: uuid.UUID,
    resolution: ReportResolution,
    notes: str | None = None,
) -> ModerationLog:
    """Close a report, and audit the closing as its own entry.

    Two rows on purpose. The report row records THAT it was resolved, so the
    queue stops offering it; the new row records WHO closed it and how, in the
    same table every other moderator action is written to — so "what did this
    moderator do last week" is still one query. Whatever was done to the
    content itself (unpublishing, restoring) is audited by the service that did
    it, and this never pretends to have done it.

    Resolving an already-resolved report is refused rather than silently
    overwritten: two moderators reaching the same report should collide loudly.
    """
    if report.resolution is not None:
        raise AppError(
            "That report has already been resolved.",
            code="report_already_resolved",
            status_code=409,
            title="Conflicting state",
        )

    report.resolution = resolution
    report.resolved_at = datetime.now(UTC)
    report.resolved_by = moderator_id

    db.add(ModerationLog(
        target_type=report.target_type,
        target_ref=report.target_ref,
        moderator_id=moderator_id,
        action=_RESOLUTION_AUDIT_ACTION[resolution],
        notes=notes,
        context={"report_id": str(report.id), "resolution": resolution.value},
    ))
    db.commit()
    db.refresh(report)
    return report


#: Which audit action each outcome writes. `approve` for a dismissal reads oddly
#: at first glance and is exactly right: the moderator looked at the content and
#: let it stand.
_RESOLUTION_AUDIT_ACTION = {
    ReportResolution.dismissed: ModerationAction.approve,
    ReportResolution.content_removed: ModerationAction.remove,
    ReportResolution.content_restored: ModerationAction.restore,
    ReportResolution.escalated: ModerationAction.escalate,
}


def report_counts(
    db: Session, target_type: ModerationTargetType, target_refs: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """How many distinct reports each target has, for badging the moderator queue.

    Every report ever filed, resolved or not. Deliberate: the badge answers "how
    contested has this been", which a dismissal does not undo, and the priority
    policy reads the same counts — narrowing them to open reports would silently
    re-score the whole queue. Whether a dismissed report should stop contributing
    to priority is a policy question for the owner, not a change to sneak in with
    a UI control.
    """
    if not target_refs:
        return {}
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


@dataclass(frozen=True)
class ReportFacts:
    """The only report information the priority policy is allowed to see: how
    many people flagged a target and which enum reasons they picked. Never the
    notes, the evidence URLs, or who reported."""

    count: int
    reasons: frozenset[ModerationReason]


#: Returned for a target that has no reports, so callers can index unconditionally.
NO_REPORTS = ReportFacts(count=0, reasons=frozenset())

_QUERY_CHUNK_SIZE = 500


def _chunks(values: Collection[uuid.UUID]) -> Iterator[tuple[uuid.UUID, ...]]:
    items = tuple(dict.fromkeys(values))
    for start in range(0, len(items), _QUERY_CHUNK_SIZE):
        yield items[start : start + _QUERY_CHUNK_SIZE]


def report_facts_by_target(
    db: Session,
    target_type: ModerationTargetType,
    target_refs: Collection[uuid.UUID],
) -> dict[uuid.UUID, ReportFacts]:
    """Batch the report count and reason set for a bounded set of targets.

    Two grouped queries over ``moderation_logs`` (action=report) — one counting
    the distinct report rows, one collecting the distinct enum reasons. Targets
    with no reports are simply absent from the result; use :data:`NO_REPORTS`
    as the default. Nothing here loads a note, an evidence URL, or a
    ``reporter_id``.
    """
    refs = list(dict.fromkeys(target_refs))
    if not refs:
        return {}

    counts: dict[uuid.UUID, int] = {}
    reasons: dict[uuid.UUID, set[ModerationReason]] = {}
    for chunk in _chunks(refs):
        count_rows = db.execute(
            select(ModerationLog.target_ref, func.count(ModerationLog.id))
            .where(
                ModerationLog.action == ModerationAction.report,
                ModerationLog.target_type == target_type,
                ModerationLog.target_ref.in_(chunk),
            )
            .group_by(ModerationLog.target_ref)
        ).all()
        counts.update((target_ref, int(count)) for target_ref, count in count_rows)

        reason_rows = db.execute(
            select(ModerationLog.target_ref, ModerationLog.reason)
            .where(
                ModerationLog.action == ModerationAction.report,
                ModerationLog.target_type == target_type,
                ModerationLog.target_ref.in_(chunk),
                ModerationLog.reason.is_not(None),
            )
            .distinct()
        ).all()
        for target_ref, reason in reason_rows:
            reasons.setdefault(target_ref, set()).add(reason)

    return {
        target_ref: ReportFacts(
            count=count,
            reasons=frozenset(reasons.get(target_ref, ())),
        )
        for target_ref, count in counts.items()
    }
