"""Seller routes (FR-4) — stores, their public ratings, and claim requests.

Reading is public: FR-2 lets anyone browse without an account. Adding a store,
rating one and claiming one each need an account. Deciding a claim is a
moderator action and lives in `admin_sellers`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.enums import Platform
from app.models.user import User
from app.schemas.seller import (
    SellerClaimCreate,
    SellerClaimOut,
    SellerCreate,
    SellerDetailOut,
    SellerOut,
    SellerReviewCreate,
    SellerReviewOut,
)
from app.services import seller_service

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.post("", response_model=SellerOut, status_code=201,
             summary="Find a store, or add it if it is new")
def add_seller(payload: SellerCreate, response: Response,
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user)) -> SellerOut:
    """201 when the store is new, 200 when an existing one matched.

    Matching is by platform and normalised name, so casing and stray spaces
    return the existing store rather than a duplicate.
    """
    seller, created = seller_service.find_or_create_seller(db, payload)
    if not created:
        response.status_code = 200
    return SellerOut.model_validate(seller)


@router.get("", response_model=list[SellerOut], summary="Search stores")
def list_sellers(db: Session = Depends(get_db),
                 q: str | None = Query(None, max_length=160),
                 platform: Platform | None = None,
                 limit: int = Query(30, ge=1, le=100)) -> list[SellerOut]:
    return seller_service.list_sellers(db, q=q, platform=platform, limit=limit)


@router.get("/{seller_id}", response_model=SellerDetailOut,
            summary="A store with its public rating summary")
def get_seller(seller_id: uuid.UUID, db: Session = Depends(get_db)) -> SellerDetailOut:
    return seller_service.get_seller_detail(db, seller_id)


@router.post("/{seller_id}/reviews", response_model=SellerReviewOut, status_code=201,
             summary="Rate a store on FR-4's four dimensions")
def rate_seller(seller_id: uuid.UUID, payload: SellerReviewCreate,
                db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> SellerReviewOut:
    seller = seller_service.get_seller_or_404(db, seller_id)
    return seller_service.create_seller_review(db, seller, user, payload)


@router.get("/{seller_id}/reviews", response_model=list[SellerReviewOut],
            summary="A store's ratings, newest first")
def list_seller_reviews(seller_id: uuid.UUID, db: Session = Depends(get_db),
                        limit: int = Query(30, ge=1, le=100)) -> list[SellerReviewOut]:
    return seller_service.list_seller_reviews(db, seller_id, limit)


@router.post("/{seller_id}/claims", response_model=SellerClaimOut, status_code=201,
             summary="Ask to be recognised as this store's owner")
def claim_seller(seller_id: uuid.UUID, payload: SellerClaimCreate,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> SellerClaimOut:
    seller = seller_service.get_seller_or_404(db, seller_id)
    return seller_service.submit_claim(db, seller, user, payload)
