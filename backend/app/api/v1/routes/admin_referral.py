"""Moderator referral/publication endpoints (M2 slice 1). All RBAC=moderator,
all mutations audit-logged in `moderation_logs`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import require_role
from app.db.session import get_db
from app.models.product import Product, ProductPlatform
from app.models.review import Review
from app.models.user import User
from app.schemas.referral import (
    AttachLinkRequest,
    OptionalReasonRequest,
    QueueAuthor,
    QueueItem,
    QueuePlatform,
    QueueProduct,
    QueueSignals,
    ReasonRequest,
    ReferralLinkOut,
    ReviewQueueResponse,
)
from app.schemas.review import ReviewOut
from app.services import fraud_service, referral_service, review_service

router = APIRouter(prefix="/admin", tags=["admin: referral"],
                   dependencies=[Depends(require_role("moderator"))])


def _queue_item(db: Session, review: Review, product: Product,
                platforms: list[ProductPlatform], author: User | None,
                *, edited: bool) -> QueueItem:
    """Build a queue card. Fraud signals (slice 5) are computed here — queue
    payload only, advisory only, never on public endpoints."""
    return QueueItem(
        review=ReviewOut.model_validate(review),
        product=QueueProduct(
            id=product.id, canonical_name=product.canonical_name,
            source_url=product.source_url,
            platforms=[QueuePlatform(platform=p.platform, is_monetizable=p.is_monetizable)
                       for p in platforms],
        ),
        author=(QueueAuthor(id=author.id, display_name=author.display_name,
                            trust_stage=author.trust_stage,
                            reputation_score=author.reputation_score) if author else None),
        suggested_platform=referral_service.suggested_platform_from(product, platforms),
        edited_since_monetized=edited,
        signals=QueueSignals(**fraud_service.compute_signals(db, review, author)),
        suggested_sub_id=referral_service.sub_id_for_review(review.id),
    )


@router.get("/review-queue", response_model=ReviewQueueResponse,
            summary="Moderator queue: pending reviews + monetized-but-edited")
def review_queue(db: Session = Depends(get_db), limit: int = 50, offset: int = 0
                 ) -> ReviewQueueResponse:
    limit = min(limit, 100)
    pending, edited = referral_service.get_queue(db, limit=limit, offset=offset)
    reviews = pending + edited

    # Batch-load products (+ their platforms) and authors — one query each, no N+1.
    product_ids = {r.product_id for r in reviews}
    products: dict = {}
    if product_ids:
        products = {p.id: p for p in db.scalars(
            select(Product).options(selectinload(Product.platforms))
            .where(Product.id.in_(product_ids)))}
    author_ids = {r.author_id for r in reviews if r.author_id}
    authors: dict = {}
    if author_ids:
        authors = {u.id: u for u in db.scalars(
            select(User).where(User.id.in_(author_ids)))}

    def build(review: Review, *, edited: bool) -> QueueItem:
        product = products[review.product_id]
        author = authors.get(review.author_id) if review.author_id else None
        return _queue_item(db, review, product, product.platforms, author, edited=edited)

    return ReviewQueueResponse(
        pending=[build(r, edited=False) for r in pending],
        edited_since_monetized=[build(r, edited=True) for r in edited],
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
