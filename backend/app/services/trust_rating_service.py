"""Product & seller Wilson trust ratings + seller reviews (M2 slice 4).

- Product trust = time_decayed_wilson over (star_rating >= 4, age) of the
  product's published, not-removed reviews. Recomputed on publish/unpublish/edit
  (via recompute_product_aggregates) and nightly.
- Seller trust = time_decayed_wilson over (would_recommend, age) of the seller's
  seller_reviews. Recomputed on each seller-review write and nightly.

Seller reviews publish immediately: no monetization is attached to them, so the
publication gate does not apply (documented deviation).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.models.enums import MemberRole
from app.models.product import Product
from app.models.review import Review
from app.models.seller_review import SellerReview
from app.models.user import User
from app.schemas.seller import SellerReviewCreate
from app.services.ranking import time_decayed_wilson
from app.services.vote_service import age_days


def _conflict(detail: str, code: str) -> AppError:
    return AppError(detail, code=code, status_code=409, title="Conflicting state")


# --- Product trust ---
def recompute_product_trust(db: Session, product_id: uuid.UUID) -> None:
    rows = db.execute(
        select(Review.star_rating, Review.created_at)
        .where(Review.product_id == product_id,
               Review.published_at.isnot(None),
               Review.is_removed.is_(False))
    ).all()
    product = db.get(Product, product_id)
    if product is not None:
        product.trust_score = time_decayed_wilson(
            (stars >= 4, age_days(created)) for stars, created in rows)


# --- Seller trust + per-dimension aggregates ---
def recompute_seller_trust(db: Session, seller_id: uuid.UUID) -> None:
    reviews = db.scalars(
        select(SellerReview).where(SellerReview.seller_id == seller_id)).all()
    seller = db.get(User, seller_id)
    if seller is None:
        return
    seller.seller_trust_score = time_decayed_wilson(
        (r.would_recommend, age_days(r.created_at)) for r in reviews)
    n = len(reviews)
    if n:
        seller.seller_aggregates = {
            "accuracy_pct": round(100.0 * sum(r.accuracy for r in reviews) / n, 2),
            "completeness_pct": round(
                100.0 * sum(r.order_completeness for r in reviews) / n, 2),
            "customer_service_avg": round(
                sum(r.customer_service for r in reviews) / n, 2),
            "packaging_avg": round(sum(r.packaging_quality for r in reviews) / n, 2),
            "recommend_pct": round(100.0 * sum(r.would_recommend for r in reviews) / n, 2),
            "count": n,
        }
    else:
        seller.seller_aggregates = None


def seller_or_404(db: Session, seller_id: uuid.UUID) -> User:
    seller = db.get(User, seller_id)
    if seller is None or seller.role != MemberRole.seller:
        raise NotFoundError("Seller not found.", code="seller_not_found")
    return seller


def create_seller_review(db: Session, seller: User, reviewer: User,
                         payload: SellerReviewCreate) -> SellerReview:
    if seller.id == reviewer.id:
        raise _conflict("You cannot review yourself as a seller.",
                        "cannot_review_self")
    existing = db.scalar(select(SellerReview.id).where(
        SellerReview.seller_id == seller.id,
        SellerReview.reviewer_id == reviewer.id))
    if existing is not None:
        raise _conflict("You have already reviewed this seller.",
                        "seller_review_exists")
    review = SellerReview(
        seller_review_id=f"srev_{uuid.uuid4().hex[:10]}",
        seller_id=seller.id, reviewer_id=reviewer.id,
        product_id=payload.product_id,
        accuracy=payload.accuracy,
        order_completeness=payload.order_completeness,
        customer_service=payload.customer_service,
        packaging_quality=payload.packaging_quality,
        overall_rating=payload.overall_rating,
        would_recommend=payload.would_recommend,
        proof_url=payload.proof_url,
    )
    db.add(review)
    try:
        db.flush()
    except IntegrityError as exc:  # uq_seller_review_once race backstop
        db.rollback()
        raise _conflict("You have already reviewed this seller.",
                        "seller_review_exists") from exc
    recompute_seller_trust(db, seller.id)
    db.commit()
    db.refresh(review)
    return review


def list_seller_reviews(db: Session, seller_id: uuid.UUID,
                        limit: int = 50) -> list[SellerReview]:
    return list(db.scalars(
        select(SellerReview).where(SellerReview.seller_id == seller_id)
        .order_by(SellerReview.created_at.desc()).limit(min(limit, 100))))


# --- Nightly sweep (extends the 04:00 wilson task) ---
def recompute_all_trust_ratings(db: Session) -> dict[str, int]:
    product_ids = db.scalars(
        select(Review.product_id).where(Review.published_at.isnot(None),
                                        Review.is_removed.is_(False)).distinct()).all()
    for product_id in product_ids:
        recompute_product_trust(db, product_id)

    seller_ids = db.scalars(select(SellerReview.seller_id).distinct()).all()
    for seller_id in seller_ids:
        recompute_seller_trust(db, seller_id)
    db.commit()
    return {"products_updated": len(product_ids), "sellers_updated": len(seller_ids)}


# --- Visibility thresholds (config-driven; defaults OFF) ---
def product_low_trust(product: Product, *, threshold: float, min_reviews: int) -> bool:
    """True iff the product has enough reviews to judge AND scores below threshold."""
    return (product.review_count >= min_reviews
            and float(product.trust_score) < threshold)


def seller_low_trust(seller: User, *, threshold: float) -> bool:
    count = (seller.seller_aggregates or {}).get("count", 0)
    return (seller.seller_trust_score is not None and count > 0
            and float(seller.seller_trust_score) < threshold)


def seller_review_count(db: Session, seller_id: uuid.UUID) -> int:
    return db.scalar(select(func.count(SellerReview.id))
                     .where(SellerReview.seller_id == seller_id)) or 0
