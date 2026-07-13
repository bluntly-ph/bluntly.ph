"""Review submission, editing (with version history), and product aggregates (M1)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError
from app.models.enums import EarnEligibleStatus, VerificationStatus
from app.models.product import Product
from app.models.review import Review, ReviewVersion
from app.schemas.review import ReviewCreate, ReviewUpdate

# Fields captured in each version snapshot.
VERSIONED_FIELDS = (
    "title", "discussion", "verdict", "verdict_explanation", "target_audience",
    "anti_target_audience", "star_rating", "pros", "cons", "photo_url",
    "receipt_url", "price_paid",
)


def _snapshot(review: Review) -> dict:
    snap: dict = {}
    for field in VERSIONED_FIELDS:
        value = getattr(review, field)
        if field == "verdict" and value is not None:
            value = value.value
        elif field == "price_paid" and value is not None:
            value = str(value)
        snap[field] = value
    return snap


def recompute_product_aggregates(db: Session, product_id: uuid.UUID) -> None:
    """Service-layer aggregate update (ADR: no DB triggers).

    Counts only **published**, non-removed reviews (publication gate, M2 slice 1).
    """
    stats = db.execute(
        select(func.count(Review.id), func.coalesce(func.avg(Review.star_rating), 0))
        .where(Review.product_id == product_id, Review.is_removed.is_(False),
               Review.published_at.isnot(None))
    ).one()
    product = db.get(Product, product_id)
    if product is not None:
        product.review_count = int(stats[0])
        product.avg_rating = round(float(stats[1]), 2)


def create_review(db: Session, author_id: uuid.UUID, payload: ReviewCreate) -> Review:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise NotFoundError("Product not found.", code="product_not_found")

    review = Review(
        product_id=payload.product_id,
        author_id=author_id,
        title=payload.title,
        discussion=payload.discussion,
        verdict=payload.verdict,
        verdict_explanation=payload.verdict_explanation,
        target_audience=payload.target_audience,
        anti_target_audience=payload.anti_target_audience,
        star_rating=payload.star_rating,
        pros=payload.pros,
        cons=payload.cons,
        photo_url=payload.photo_url,
        receipt_url=payload.receipt_url,
        price_paid=payload.price_paid,
        # Proof photo at submission => verified (FR-3).
        verification_status=(VerificationStatus.verified if payload.photo_url
                             else VerificationStatus.unverified),
        review_id=f"rev_{uuid.uuid4().hex[:10]}",
        current_version=1,
        # Publication gate (M2 slice 1): hidden + auto-queued for the moderator.
        published_at=None,
        earn_eligible_status=(EarnEligibleStatus.pending if settings.earn_eligible_auto_queue
                              else EarnEligibleStatus.none),
    )
    db.add(review)
    db.flush()
    db.add(ReviewVersion(review_id=review.id, version_number=1,
                         snapshot=_snapshot(review), edited_by=author_id,
                         change_note="initial submission"))
    # New review is unpublished, so aggregates are unchanged; recompute is a no-op
    # here but harmless and keeps the invariant obvious.
    recompute_product_aggregates(db, review.product_id)
    db.commit()
    db.refresh(review)
    return review


def update_review(db: Session, review: Review, editor_id: uuid.UUID,
                  payload: ReviewUpdate) -> Review:
    data = payload.model_dump(exclude_unset=True)
    change_note = data.pop("change_note", None)

    changed = False
    for field, value in data.items():
        if getattr(review, field) != value:
            setattr(review, field, value)
            changed = True

    if not changed:
        return review  # no-op edit: don't create an empty version

    # Re-derive verification from the (possibly changed) photo.
    review.verification_status = (VerificationStatus.verified if review.photo_url
                                  else VerificationStatus.unverified)
    # A rejected review that gets edited is re-queued for moderation (still hidden).
    if review.earn_eligible_status == EarnEligibleStatus.rejected:
        review.earn_eligible_status = EarnEligibleStatus.pending
    review.current_version += 1
    db.add(ReviewVersion(review_id=review.id, version_number=review.current_version,
                         snapshot=_snapshot(review), edited_by=editor_id,
                         change_note=change_note))
    recompute_product_aggregates(db, review.product_id)
    db.commit()
    db.refresh(review)
    return review


def get_review_or_404(db: Session, review_id: uuid.UUID) -> Review:
    review = db.get(Review, review_id)
    if review is None or review.is_removed:
        raise NotFoundError("Review not found.", code="review_not_found")
    return review


def list_versions(db: Session, review_id: uuid.UUID) -> list[ReviewVersion]:
    return list(db.scalars(
        select(ReviewVersion).where(ReviewVersion.review_id == review_id)
        .order_by(ReviewVersion.version_number)
    ))
