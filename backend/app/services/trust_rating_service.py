"""Product Wilson trust ratings (M2 slice 4).

Product trust = time_decayed_wilson over (star_rating >= 4, age) of the
product's published, not-removed reviews. Recomputed on publish/unpublish/edit
(via recompute_product_aggregates) and nightly.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.review import Review
from app.services.ranking import time_decayed_wilson
from app.services.vote_service import age_days


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


# --- Nightly sweep (extends the 04:00 wilson task) ---
def reviewed_product_ids(db: Session) -> list:
    """Products carrying at least one live published review — the population
    the nightly rating sweep walks. Named for the same reason as the others."""
    return list(db.scalars(
        select(Review.product_id).where(Review.published_at.isnot(None),
                                        Review.is_removed.is_(False)).distinct()).all())


def recompute_all_trust_ratings(db: Session) -> dict[str, int]:
    product_ids = reviewed_product_ids(db)
    for product_id in product_ids:
        recompute_product_trust(db, product_id)
    db.commit()
    return {"products_updated": len(product_ids)}


# --- Visibility thresholds (config-driven; defaults OFF) ---
def product_low_trust(product: Product, *, threshold: float, min_reviews: int) -> bool:
    """True iff the product has enough reviews to judge AND scores below threshold."""
    return (product.review_count >= min_reviews
            and float(product.trust_score) < threshold)
