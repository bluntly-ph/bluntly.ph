"""Moderator view of community content reports (FR-9). RBAC=moderator.

Reports live in `moderation_logs` (action=report). This route reads that queue
and joins the minimum context a moderator needs to act — who reported, what was
reported, and how many separate people have flagged the same target.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.enums import ModerationTargetType
from app.models.review import Review
from app.models.user import User
from app.schemas.report import ReportOut
from app.services import report_service

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
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ReportQueueResponse:
    limit = min(limit, 100)
    logs = report_service.list_reports(
        db, target_type=target_type, limit=limit, offset=offset
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
