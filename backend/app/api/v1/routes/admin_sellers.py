"""Seller claim moderation (FR-4, FR-9) — moderator only.

The whole router is guarded by `require_role("moderator")`, so neither a
`seller` nor an ordinary `user` can reach it: a store owner approving their
own claim is the failure this workflow exists to prevent. The service adds the
narrower rule that a moderator cannot decide a claim they submitted.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.seller import ClaimDecision, SellerClaimOut
from app.services import seller_service

router = APIRouter(prefix="/admin/seller-claims", tags=["admin"],
                   dependencies=[Depends(require_role("moderator"))])


@router.get("", response_model=list[SellerClaimOut],
            summary="Seller claims waiting for a decision, oldest first")
def pending_claims(db: Session = Depends(get_db),
                   limit: int = Query(50, ge=1, le=200)) -> list[SellerClaimOut]:
    return seller_service.list_pending_claims(db, limit)


@router.post("/{claim_id}/decision", response_model=SellerClaimOut,
             summary="Approve or reject a seller claim")
def decide_claim(claim_id: uuid.UUID, decision: ClaimDecision,
                 db: Session = Depends(get_db),
                 moderator: User = Depends(get_current_user)) -> SellerClaimOut:
    return seller_service.decide_claim(db, claim_id, moderator, decision)
