"""Review contract endpoints (M3 slice 10).

A contract is created automatically when a review is first monetized; there is no
create endpoint. Reviewers control auto-renew and answer buyout offers;
moderators offer buyouts and watch expiries.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import ContractStatus
from app.models.user import User
from app.schemas.contract import AutoRenewUpdate, BuyoutOffer, ContractOut
from app.services import contract_service

router = APIRouter(tags=["contracts"])


@router.get("/contracts", response_model=list[ContractOut],
            summary="Your revenue-share contracts")
def list_own(db: Session = Depends(get_db), user: User = Depends(get_current_user),
             limit: int = Query(50, ge=1, le=100)) -> list[ContractOut]:
    return [ContractOut.model_validate(c)
            for c in contract_service.list_own(db, user.id, limit)]


@router.patch("/contracts/{contract_id}/auto-renew", response_model=ContractOut,
              summary="Turn auto-renewal on or off (contract owner)")
def set_auto_renew(contract_id: uuid.UUID, payload: AutoRenewUpdate,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> ContractOut:
    contract = contract_service.get_or_404(db, contract_id)
    return ContractOut.model_validate(
        contract_service.set_auto_renew(db, contract, user, payload.auto_renew))


@router.post("/contracts/{contract_id}/buyout/accept", response_model=ContractOut,
             summary="Accept the pending buyout (credits your wallet; ends the contract)")
def accept_buyout(contract_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ContractOut:
    contract = contract_service.get_or_404(db, contract_id)
    return ContractOut.model_validate(contract_service.accept_buyout(db, contract, user))


@router.post("/contracts/{contract_id}/buyout/reject", response_model=ContractOut,
             summary="Reject the pending buyout (contract continues unchanged)")
def reject_buyout(contract_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ContractOut:
    contract = contract_service.get_or_404(db, contract_id)
    return ContractOut.model_validate(contract_service.reject_buyout(db, contract, user))


@router.get("/admin/contracts", response_model=list[ContractOut],
            summary="All contracts (moderator; filter by status / expiry window)")
def admin_list(db: Session = Depends(get_db),
               mod: User = Depends(require_role("moderator")),
               status: ContractStatus | None = None,
               expiring_within_days: int | None = Query(None, ge=0, le=365),
               limit: int = Query(50, ge=1, le=100)) -> list[ContractOut]:
    return [ContractOut.model_validate(c) for c in
            contract_service.list_admin(db, status, expiring_within_days, limit)]


@router.post("/admin/contracts/{contract_id}/buyout", response_model=ContractOut,
             summary="Offer a buyout (moderator; one pending offer at a time)")
def offer_buyout(contract_id: uuid.UUID, payload: BuyoutOffer,
                 db: Session = Depends(get_db),
                 mod: User = Depends(require_role("moderator"))) -> ContractOut:
    contract = contract_service.get_or_404(db, contract_id)
    return ContractOut.model_validate(
        contract_service.offer_buyout(db, contract, mod.id, payload.amount))
