"""Seller moderation (FR-4, FR-9) — moderator only.

The whole router is guarded by `require_role("moderator")`, so neither a
`seller` nor an ordinary `user` can reach it: a store owner approving their
own claim, or removing the ratings of their own store, is the failure this
workflow exists to prevent. The service adds the narrower rule that a moderator
cannot decide a claim they submitted, nor remove a rating they wrote or one of
a store they run.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.seller import ClaimDecision, SellerClaimOut, SellerReviewOut, SellerReviewRemoval
from app.services import seller_service

router = APIRouter(prefix="/admin", tags=["admin"],
                   dependencies=[Depends(require_role("moderator"))])


@router.get("/seller-claims", response_model=list[SellerClaimOut],
            summary="Seller claims waiting for a decision, oldest first")
def pending_claims(db: Session = Depends(get_db),
                   limit: int = Query(50, ge=1, le=200)) -> list[SellerClaimOut]:
    return seller_service.list_pending_claims(db, limit)


@router.post("/seller-claims/{claim_id}/decision", response_model=SellerClaimOut,
             summary="Approve or reject a seller claim")
def decide_claim(claim_id: uuid.UUID, decision: ClaimDecision,
                 db: Session = Depends(get_db),
                 moderator: User = Depends(get_current_user)) -> SellerClaimOut:
    return seller_service.decide_claim(db, claim_id, moderator, decision)


@router.post("/seller-reviews/{review_id}/removal", response_model=SellerReviewOut,
             summary="Remove a seller review from the store's page and numbers")
def remove_seller_review(review_id: uuid.UUID, payload: SellerReviewRemoval,
                         db: Session = Depends(get_db),
                         moderator: User = Depends(get_current_user)) -> SellerReviewOut:
    return seller_service.remove_seller_review(db, review_id, moderator, payload.note)
