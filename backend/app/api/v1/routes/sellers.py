"""Seller reviews + public seller profiles (M2 slice 4).

Seller reviews publish immediately (no monetization attached, so the review
publication gate does not apply — documented deviation). A low seller trust
score only flags the profile (`low_trust`) — it is never hidden.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.seller import SellerReviewCreate, SellerReviewOut
from app.schemas.user import SellerProfileOut
from app.services import trust_rating_service

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.post("/{seller_id}/reviews", response_model=SellerReviewOut, status_code=201,
             summary="Review a seller (one per reviewer; publishes immediately)")
def create_seller_review(seller_id: uuid.UUID, payload: SellerReviewCreate,
                         db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)) -> SellerReviewOut:
    seller = trust_rating_service.seller_or_404(db, seller_id)
    review = trust_rating_service.create_seller_review(db, seller, user, payload)
    return SellerReviewOut.model_validate(review)


@router.get("/{seller_id}/reviews", response_model=list[SellerReviewOut],
            summary="List a seller's reviews (newest first)")
def list_seller_reviews(seller_id: uuid.UUID, db: Session = Depends(get_db),
                        limit: int = Query(50, ge=1, le=100)) -> list[SellerReviewOut]:
    trust_rating_service.seller_or_404(db, seller_id)
    return [SellerReviewOut.model_validate(r)
            for r in trust_rating_service.list_seller_reviews(db, seller_id, limit)]


@router.get("/{seller_id}", response_model=SellerProfileOut,
            summary="Public seller profile with trust rating + dimension averages")
def seller_profile(seller_id: uuid.UUID, db: Session = Depends(get_db)) -> SellerProfileOut:
    seller = trust_rating_service.seller_or_404(db, seller_id)
    aggregates = seller.seller_aggregates or {}
    return SellerProfileOut(
        id=seller.id,
        display_name=seller.display_name,
        seller_trust_score=seller.seller_trust_score,
        low_trust=trust_rating_service.seller_low_trust(
            seller, threshold=settings.seller_trust_visibility_threshold),
        review_count=aggregates.get("count", 0),
        accuracy_pct=aggregates.get("accuracy_pct"),
        completeness_pct=aggregates.get("completeness_pct"),
        customer_service_avg=aggregates.get("customer_service_avg"),
        packaging_avg=aggregates.get("packaging_avg"),
        recommend_pct=aggregates.get("recommend_pct"),
    )
