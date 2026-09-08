"""Moderator referral/publication endpoints (M2 slice 1). All RBAC=moderator,
all mutations audit-logged in `moderation_logs`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.referral import (
    AttachLinkRequest,
    OptionalReasonRequest,
    ReasonRequest,
    ReferralLinkOut,
    ReviewQueueResponse,
)
from app.schemas.review import ReviewOut
from app.services import referral_service, review_service
from app.services.moderation_priority import PriorityBand, PriorityLane, SlaState

router = APIRouter(prefix="/admin", tags=["admin: referral"],
                   dependencies=[Depends(require_role("moderator"))])


@router.get("/review-queue", response_model=ReviewQueueResponse,
            summary="Moderator queue: policy-prioritized reviews (+ deprecated split views)")
def review_queue(
    db: Session = Depends(get_db),
    band: PriorityBand | None = Query(None, description="Filter to one priority band."),
    lane: PriorityLane | None = Query(None, description="Filter to one routing lane."),
    sla: SlaState | None = Query(None, description="Filter to one SLA state."),
    factor: str | None = Query(None, max_length=64,
                               description="Filter to cards carrying this factor code."),
    q: str | None = Query(None, max_length=200,
                          description="Free-text match on review title/body or product."),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ReviewQueueResponse:
    limit = min(limit, 100)
    query = referral_service.QueueQuery(
        band=band, lane=lane, sla=sla, factor=factor, q=q, limit=limit, offset=offset,
    )
    page = referral_service.get_prioritized_queue(db, query)

    # Deprecated duplicate views: same membership, ordering and offset paging as
    # before, so existing callers (and the Next client, until Task 4) keep
    # working. Removed once `items` is the only consumer.
    pending, edited = referral_service.get_queue(db, limit=limit, offset=offset)
    legacy = referral_service.build_queue_items(
        db, [(r, "pending") for r in pending] + [(r, "edited") for r in edited],
    )

    return ReviewQueueResponse(
        items=page.items,
        total=page.total,
        next_cursor=page.next_cursor,
        counts=page.counts,
        pending=[legacy[r.id] for r in pending],
        edited_since_monetized=[legacy[r.id] for r in edited],
    )


@router.post("/reviews/{review_id}/referral-link", response_model=ReviewOut,
             summary="Paste referral link -> monetize + publish (atomic)")
def attach_link(review_id: uuid.UUID, payload: AttachLinkRequest,
                db: Session = Depends(get_db),
                mod: User = Depends(require_role("moderator"))) -> ReviewOut:
    review = review_service.get_review_or_404(db, review_id)
    review = referral_service.attach_link_and_publish(db, review, mod.id,
                                                      payload.url, payload.platform,
                                                      sub_id=payload.sub_id)
    return ReviewOut.model_validate(review)


@router.delete("/reviews/{review_id}/referral-link", response_model=ReviewOut,
               summary="Revoke the active referral link (stays published)")
def revoke_link(review_id: uuid.UUID, payload: ReasonRequest,
                db: Session = Depends(get_db),
                mod: User = Depends(require_role("moderator"))) -> ReviewOut:
    review = review_service.get_review_or_404(db, review_id)
    review = referral_service.revoke_link(db, review, mod.id, payload.reason)
    return ReviewOut.model_validate(review)


@router.post("/reviews/{review_id}/publish", response_model=ReviewOut,
             summary="Publish without a link (<=2* -> Honesty Fund, else approved)")
def publish(review_id: uuid.UUID, db: Session = Depends(get_db),
            mod: User = Depends(require_role("moderator"))) -> ReviewOut:
    review = review_service.get_review_or_404(db, review_id)
    review = referral_service.publish_without_link(db, review, mod.id)
    return ReviewOut.model_validate(review)


@router.post("/reviews/{review_id}/reject", response_model=ReviewOut,
             summary="Reject a queued review (stays hidden; author may resubmit)")
def reject(review_id: uuid.UUID, payload: ReasonRequest, db: Session = Depends(get_db),
           mod: User = Depends(require_role("moderator"))) -> ReviewOut:
    review = review_service.get_review_or_404(db, review_id)
    review = referral_service.reject(db, review, mod.id, payload.reason)
    return ReviewOut.model_validate(review)


@router.post("/reviews/{review_id}/unpublish", response_model=ReviewOut,
             summary="Take a published review off the public site")
def unpublish(review_id: uuid.UUID, payload: OptionalReasonRequest,
              db: Session = Depends(get_db),
              mod: User = Depends(require_role("moderator"))) -> ReviewOut:
    review = review_service.get_review_or_404(db, review_id)
    review = referral_service.unpublish(db, review, mod.id, payload.reason)
    return ReviewOut.model_validate(review)


@router.get("/reviews/{review_id}/referral-links", response_model=list[ReferralLinkOut],
            summary="Referral link history for a review")
def link_history(review_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ReferralLinkOut]:
    review_service.get_review_or_404(db, review_id)
    return [ReferralLinkOut.model_validate(link)
            for link in referral_service.list_links(db, review_id)]
