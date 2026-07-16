"""Payout endpoints (M3 slice 11).

Manual mode is always available: a moderator can mark a payout paid with the
provider reference from their own PayPal dashboard, so payouts work end-to-end
without any API credentials.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import PayoutMethod, PayoutStatus
from app.models.user import User
from app.schemas.referral import ReasonRequest
from app.services import payout_service

router = APIRouter(tags=["payouts"])


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payout_id: str | None = None
    user_id: uuid.UUID
    amount: Decimal
    currency: str
    status: PayoutStatus
    method: PayoutMethod
    provider_ref: str | None = None
    batch_id: str | None = None
    scheduled_for: date
    paid_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime


class PayoutAccountUpdate(BaseModel):
    payout_account: EmailStr


class MarkPaidRequest(BaseModel):
    provider_ref: str = Field(min_length=1, max_length=128)


class RunRequest(BaseModel):
    submit: bool = Field(default=False,
                         description="Also hand the batch to the provider now.")


@router.patch("/auth/me/payout-account", summary="Set where your payouts are sent")
def set_payout_account(payload: PayoutAccountUpdate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> dict:
    user.payout_account = str(payload.payout_account)
    db.commit()
    return {"payout_account": user.payout_account}


@router.get("/payouts", response_model=list[PayoutOut], summary="Your payouts")
def list_own(db: Session = Depends(get_db), user: User = Depends(get_current_user),
             limit: int = Query(50, ge=1, le=100)) -> list[PayoutOut]:
    return [PayoutOut.model_validate(p) for p in payout_service.list_own(db, user.id, limit)]


@router.get("/admin/payouts", response_model=list[PayoutOut],
            summary="All payouts (moderator)")
def admin_list(db: Session = Depends(get_db),
               mod: User = Depends(require_role("moderator")),
               status: PayoutStatus | None = None, batch_id: str | None = None,
               limit: int = Query(50, ge=1, le=100)) -> list[PayoutOut]:
    return [PayoutOut.model_validate(p)
            for p in payout_service.list_admin(db, status, batch_id, limit)]


@router.post("/admin/payouts/run", summary="Run the payout scheduler now (moderator)")
def run_scheduler(payload: RunRequest, db: Session = Depends(get_db),
                  mod: User = Depends(require_role("moderator"))) -> dict:
    result = payout_service.schedule_payouts(db, triggered_by=mod.id)
    if payload.submit and result["scheduled"]:
        result["submission"] = payout_service.submit_batch(db, result["batch_id"])
    return result


@router.post("/admin/payouts/{payout_id}/mark-paid", response_model=PayoutOut,
             summary="Mark a payout paid by hand (moderator; manual rail)")
def mark_paid(payout_id: uuid.UUID, payload: MarkPaidRequest,
              db: Session = Depends(get_db),
              mod: User = Depends(require_role("moderator"))) -> PayoutOut:
    payout = payout_service.get_or_404(db, payout_id)
    return PayoutOut.model_validate(
        payout_service.mark_paid(db, payout, provider_ref=payload.provider_ref))


@router.post("/admin/payouts/{payout_id}/fail", response_model=PayoutOut,
             summary="Mark a payout failed (moderator; refunds the wallet)")
def mark_failed(payout_id: uuid.UUID, payload: ReasonRequest,
                db: Session = Depends(get_db),
                mod: User = Depends(require_role("moderator"))) -> PayoutOut:
    payout = payout_service.get_or_404(db, payout_id)
    return PayoutOut.model_validate(
        payout_service.mark_failed(db, payout, reason=payload.reason))


@router.post("/admin/payouts/{payout_id}/retry", response_model=PayoutOut,
             summary="Retry a failed payout (moderator)")
def retry(payout_id: uuid.UUID, db: Session = Depends(get_db),
          mod: User = Depends(require_role("moderator"))) -> PayoutOut:
    payout = payout_service.get_or_404(db, payout_id)
    return PayoutOut.model_validate(payout_service.retry(db, payout))


@router.post("/admin/payouts/{payout_id}/cancel", response_model=PayoutOut,
             summary="Cancel a scheduled payout (moderator; refunds the wallet)")
def cancel(payout_id: uuid.UUID, db: Session = Depends(get_db),
           mod: User = Depends(require_role("moderator"))) -> PayoutOut:
    payout = payout_service.get_or_404(db, payout_id)
    return PayoutOut.model_validate(payout_service.cancel(db, payout))


@router.post("/admin/payouts/batches/{batch_id}/refresh",
             summary="Poll the provider and settle a batch (moderator)")
def refresh_batch(batch_id: str, db: Session = Depends(get_db),
                  mod: User = Depends(require_role("moderator"))) -> dict:
    return payout_service.refresh_batch(db, batch_id)
