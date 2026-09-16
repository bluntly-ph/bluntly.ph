"""Moderator view of community content reports (FR-9). RBAC=moderator.

Reports live in `moderation_logs` (action=report). This route reads that queue
and joins the minimum context a moderator needs to act — who reported, what was
reported, and how many separate people have flagged the same target.

Resolving is here too (owner §30, 2026-09-16). Before it, this was a screen a
moderator could read and not answer: every report ever filed stayed in the
queue, whatever anyone did about it.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import ModerationTargetType, ReportResolution
from app.models.moderation import ModerationLog
from app.models.review import Review
from app.models.user import User
from app.schemas.report import ReportOut
from app.services import referral_service, report_service

router = APIRouter(prefix="/admin", tags=["admin: reports"],
                   dependencies=[Depends(require_role("moderator"))])


class ReportReporter(BaseModel):
    id: uuid.UUID
    display_name: str | None = None
    username: str | None = None
    trust_stage: int


class ReportTarget(BaseModel):
    """Enough of the reported item to triage without a second round-trip."""

    id: uuid.UUID
    title: str | None = None
    author_id: uuid.UUID | None = None
    is_published: bool = False


class ReportItem(BaseModel):
    report: ReportOut
    reporter: ReportReporter | None = None
    target: ReportTarget | None = None
    # How many distinct reports this same target has attracted. One angry reader
    # is noise; five independent reports is a signal, and the moderator should
    # see the difference without running a query.
    target_report_count: int = 1


class ReportQueueResponse(BaseModel):
    items: list[ReportItem]
    total: int


@router.get("/reports", response_model=ReportQueueResponse,
            summary="Moderator queue: community content reports")
def report_queue(
    db: Session = Depends(get_db),
    target_type: ModerationTargetType | None = Query(
        default=None, description="Filter to one content type."
    ),
    status: Literal["open", "resolved", "all"] = Query(
        default="open",
        description="Open reports (the default), resolved ones, or both.",
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ReportQueueResponse:
    limit = min(limit, 100)
    logs = report_service.list_reports(
        db, target_type=target_type, status=status, limit=limit, offset=offset
    )

    # Batch-load reporters and reviewed targets — one query each, no N+1.
    reporter_ids = {log.reporter_id for log in logs if log.reporter_id}
    reporters: dict[uuid.UUID, User] = {}
    if reporter_ids:
        reporters = {
            u.id: u
            for u in db.scalars(select(User).where(User.id.in_(reporter_ids))).all()
        }

    review_refs = [
        log.target_ref
        for log in logs
        if log.target_type == ModerationTargetType.review and log.target_ref
    ]
    reviews: dict[uuid.UUID, Review] = {}
    if review_refs:
        reviews = {
            r.id: r
            for r in db.scalars(select(Review).where(Review.id.in_(review_refs))).all()
        }
    counts = report_service.report_counts(
        db, ModerationTargetType.review, review_refs
    )

    items: list[ReportItem] = []
    for log in logs:
        reporter = reporters.get(log.reporter_id) if log.reporter_id else None
        target: ReportTarget | None = None
        if log.target_type == ModerationTargetType.review and log.target_ref:
            review = reviews.get(log.target_ref)
            if review is not None:
                target = ReportTarget(
                    id=review.id,
                    title=review.title,
                    author_id=review.author_id,
                    is_published=review.published_at is not None,
                )
        items.append(
            ReportItem(
                report=ReportOut.model_validate(log),
                reporter=(
                    ReportReporter(
                        id=reporter.id,
                        display_name=reporter.display_name,
                        username=reporter.username,
                        trust_stage=reporter.trust_stage,
                    )
                    if reporter
                    else None
                ),
                target=target,
                target_report_count=(
                    counts.get(log.target_ref, 1) if log.target_ref else 1
                ),
            )
        )

    return ReportQueueResponse(items=items, total=len(items))


class ReportDecision(BaseModel):
    """A moderator's answer to one report."""

    resolution: ReportResolution
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Why. Recorded in the audit log; not shown to the reporter.",
    )


@router.post("/reports/{report_id}/decision", response_model=ReportItem,
             summary="Resolve a report: dismiss, remove, restore or escalate")
def decide_report(
    report_id: uuid.UUID,
    payload: ReportDecision,
    db: Session = Depends(get_db),
    moderator: User = Depends(get_current_user),
) -> ReportItem:
    """Close a report, and carry out the content decision it implies.

    The two content outcomes are not recorded here and performed elsewhere —
    they are performed, through the same services the review routes use, so an
    unpublish from this screen is indistinguishable from any other unpublish:
    same audit entry, same author notification, same return to the queue.

      dismissed          the content stands. Nothing is done to it.
      content_removed    the reported review is unpublished (and therefore
                         re-queued for a decision, as `unpublish` defines).
      content_restored   the reported review is published again.
      escalated          nothing is done to the content; the report is marked
                         for a senior decision and leaves the open queue.

    The content action runs first and commits; the report is closed after it.
    So a resolution that cannot be carried out — a review already down, a target
    with no publish state — leaves the report OPEN rather than closing it over
    something that did not happen. The reverse order would be worse: a closed
    report over live content nobody is looking at any more.
    """
    report = report_service.get_report_or_404(db, report_id)

    if payload.resolution in _CONTENT_ACTIONS:
        _apply_content_decision(db, report, payload, moderator)

    resolved = report_service.resolve_report(
        db, report, moderator_id=moderator.id,
        resolution=payload.resolution, notes=payload.notes,
    )
    return _item_for(db, resolved)


#: The two outcomes that touch the content itself.
_CONTENT_ACTIONS = frozenset(
    {ReportResolution.content_removed, ReportResolution.content_restored}
)


def _apply_content_decision(db: Session, report: ModerationLog,
                            payload: ReportDecision, moderator: User) -> None:
    """Unpublish or republish the reported review, or refuse the resolution.

    Only reviews can be acted on this way today — answers, questions, sellers
    and users are reportable but have no publish state this route can move. A
    report on one of those can still be dismissed or escalated, which is the
    honest set of answers rather than a button that quietly does nothing.
    """
    if report.target_type != ModerationTargetType.review or report.target_ref is None:
        raise AppError(
            "Only a reported review can be removed or restored from here.",
            code="report_target_not_actionable",
            status_code=422,
            title="Unprocessable content",
        )
    review = db.get(Review, report.target_ref)
    if review is None:
        raise NotFoundError("The reported review no longer exists.",
                            code="review_not_found")

    if payload.resolution is ReportResolution.content_removed:
        referral_service.unpublish(db, review, moderator.id, payload.notes)
    else:
        referral_service.publish_without_link(db, review, moderator.id)


def _item_for(db: Session, log: ModerationLog) -> ReportItem:
    """One report, with the same context the queue serves."""
    reporter = db.get(User, log.reporter_id) if log.reporter_id else None
    target: ReportTarget | None = None
    if log.target_type == ModerationTargetType.review and log.target_ref:
        review = db.get(Review, log.target_ref)
        if review is not None:
            target = ReportTarget(
                id=review.id,
                title=review.title,
                author_id=review.author_id,
                is_published=review.published_at is not None,
            )
    counts = report_service.report_counts(
        db, ModerationTargetType.review,
        [log.target_ref] if log.target_ref else [],
    )
    return ReportItem(
        report=ReportOut.model_validate(log),
        reporter=(
            ReportReporter(
                id=reporter.id,
                display_name=reporter.display_name,
                username=reporter.username,
                trust_stage=reporter.trust_stage,
            )
            if reporter
            else None
        ),
        target=target,
        target_report_count=counts.get(log.target_ref, 1) if log.target_ref else 1,
    )
