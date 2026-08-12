"""Request board (M3 slice 9).

There is no money flow here any more. Posting a request used to escrow a token
bounty which was refunded on cancel/expire/remove and paid out with a
platform-minted top-up on fulfilment; tokens were retired in favour of the PHP
revenue share, and this board was the last thing still spending them
(migration 0022).

So a request is now a free demand signal: you ask, others up-vote to say they
want it too, and whoever writes the review earns through the ordinary revenue
share like any other review. Up-votes rank the board instead of raising a purse.

The historical ledger is untouched and still readable — see the migration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, NotFoundError
from app.models.enums import (
    ModerationAction,
    ModerationTargetType,
    RequestStatus,
)
from app.models.moderation import ModerationLog
from app.models.product import Product
from app.models.request_board import RequestUpvote, ReviewRequest
from app.models.review import Review
from app.models.user import User
from app.schemas.request_board import RequestCreate
from app.services.ai_critique import get_provider


def _now() -> datetime:
    return datetime.now(UTC)


def _conflict(detail: str, code: str) -> AppError:
    return AppError(detail, code=code, status_code=409, title="Conflicting state")


def get_or_404(db: Session, request_id: uuid.UUID) -> ReviewRequest:
    req = db.get(ReviewRequest, request_id)
    if req is None or req.status == RequestStatus.removed:
        raise NotFoundError("Request not found.", code="request_not_found")
    return req


def create_request(db: Session, requester: User, payload: RequestCreate) -> ReviewRequest:
    if payload.product_id is not None and db.get(Product, payload.product_id) is None:
        raise NotFoundError("Product not found.", code="product_not_found")

    # AI screening is blocking at creation; the verdict is stored either way.
    verdict = get_provider().validate_request(payload.title, payload.details,
                                              payload.source_url)
    if not verdict.valid:
        raise AppError("This request needs more detail before it can be posted.",
                       code="request_invalid", status_code=422,
                       title="Request rejected by validation",
                       extra={"reasons": verdict.reasons})

    req = ReviewRequest(
        request_id=f"req_{uuid.uuid4().hex[:10]}",
        requester_id=requester.id, product_id=payload.product_id,
        title=payload.title, details=payload.details, source_url=payload.source_url,
        status=RequestStatus.open,
        expires_at=_now() + timedelta(days=settings.request_ttl_days),
        upvote_count=0, ai_validation=verdict.model_dump(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def cancel_request(db: Session, req: ReviewRequest, user: User) -> ReviewRequest:
    if req.requester_id != user.id:
        raise AppError("Only the requester may cancel this request.",
                       code="not_request_owner", status_code=403,
                       title="Insufficient permissions")
    if req.status != RequestStatus.open:
        raise _conflict("Only an open request can be cancelled.", "request_not_open")
    req.status = RequestStatus.cancelled
    db.commit()
    db.refresh(req)
    return req


def remove_request(db: Session, req: ReviewRequest, moderator_id: uuid.UUID,
                   reason: str) -> ReviewRequest:
    if req.status in (RequestStatus.removed, RequestStatus.fulfilled):
        raise _conflict("This request can no longer be removed.", "request_not_removable")
    req.status = RequestStatus.removed
    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        target_type=ModerationTargetType.review, target_ref=req.id,
        moderator_id=moderator_id, action=ModerationAction.remove, notes=reason,
        context={"kind": "review_request", "upvotes": req.upvote_count},
    ))
    db.commit()
    db.refresh(req)
    return req


def upvote(db: Session, req: ReviewRequest, user: User) -> ReviewRequest:
    if req.status != RequestStatus.open:
        raise _conflict("Only an open request can be up-voted.", "request_not_open")
    if req.requester_id == user.id:
        raise _conflict("You cannot up-vote your own request.",
                        "cannot_upvote_own_request")
    db.add(RequestUpvote(request_id=req.id, user_id=user.id))
    try:
        db.flush()
    except IntegrityError as exc:  # uq_request_upvote_once
        db.rollback()
        raise _conflict("You have already up-voted this request.",
                        "already_upvoted") from exc
    _recount_upvotes(db, req)
    db.commit()
    db.refresh(req)
    return req


def remove_upvote(db: Session, req: ReviewRequest, user_id: uuid.UUID) -> ReviewRequest:
    existing = db.scalar(select(RequestUpvote).where(
        RequestUpvote.request_id == req.id, RequestUpvote.user_id == user_id))
    if existing is None:
        raise NotFoundError("You have not up-voted this request.",
                            code="upvote_not_found")
    db.delete(existing)
    db.flush()
    _recount_upvotes(db, req)
    db.commit()
    db.refresh(req)
    return req


def _recount_upvotes(db: Session, req: ReviewRequest) -> None:
    req.upvote_count = db.scalar(
        select(func.count(RequestUpvote.id)).where(
            RequestUpvote.request_id == req.id)) or 0


def fulfill(db: Session, req: ReviewRequest, user: User,
            review_id: uuid.UUID) -> ReviewRequest:
    """Claim a request with your own PUBLISHED review.

    Nothing is paid out here. Fulfilment marks the request answered and links the
    review; the reviewer earns from that review through the ordinary revenue
    share, exactly as they would have without a request behind it.
    """
    if req.status != RequestStatus.open:
        raise _conflict("This request is no longer open.", "request_not_open")
    review = db.get(Review, review_id)
    if review is None or review.is_removed:
        raise NotFoundError("Review not found.", code="review_not_found")
    if review.author_id != user.id:
        raise _conflict("You can only fulfill a request with your own review.",
                        "not_review_author")
    if review.published_at is None:
        raise _conflict("The review must be published by a moderator before it can "
                        "fulfill a request.", "review_not_published")
    if req.product_id is not None and review.product_id != req.product_id:
        raise _conflict("The review is for a different product than the request.",
                        "product_mismatch")

    req.status = RequestStatus.fulfilled
    req.fulfilled_by_review_id = review.id
    db.commit()
    db.refresh(req)
    return req


def list_requests(db: Session, status: RequestStatus | None = None,
                  sort: str = "newest", limit: int = 50) -> list[ReviewRequest]:
    stmt = select(ReviewRequest).where(ReviewRequest.status != RequestStatus.removed)
    if status is not None:
        stmt = stmt.where(ReviewRequest.status == status)
    if sort == "demand":
        # Most-wanted first. This replaced a sort by bounty + top-up when the
        # board stopped charging for requests; up-votes were always the better
        # signal anyway, since they say how many people want the answer rather
        # than how many tokens one person happened to have.
        stmt = stmt.order_by(ReviewRequest.upvote_count.desc(),
                             ReviewRequest.created_at.desc())
    else:
        stmt = stmt.order_by(ReviewRequest.created_at.desc())
    return list(db.scalars(stmt.limit(min(limit, 100))))


def expire_open_requests(db: Session) -> int:
    """Nightly sweep: open requests past expires_at -> expired."""
    due = db.scalars(select(ReviewRequest).where(
        ReviewRequest.status == RequestStatus.open,
        ReviewRequest.expires_at <= _now())).all()
    for req in due:
        req.status = RequestStatus.expired
    db.commit()
    return len(due)
