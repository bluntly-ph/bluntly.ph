"""Token economy endpoints (M2 slice 7): own balance + history, admin grants.

The ledger is append-only — there are intentionally no update/delete endpoints.
Spending rules are M3.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import TokenKind
from app.models.user import User
from app.services import token_service

router = APIRouter(tags=["tokens"])


class TokenBalanceOut(BaseModel):
    user_id: uuid.UUID
    token_balance: int


class TokenTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: int
    balance_after: int
    kind: TokenKind
    ref_type: str | None = None
    ref_id: uuid.UUID | None = None
    note: str | None = None
    created_at: datetime


class AdminTokenGrant(BaseModel):
    amount: int = Field(description="Signed; positive grants, negative deducts. Non-zero.")
    note: str = Field(min_length=1, max_length=500)


@router.get("/tokens/balance", response_model=TokenBalanceOut,
            summary="Your token balance")
def get_balance(user: User = Depends(get_current_user)) -> TokenBalanceOut:
    return TokenBalanceOut(user_id=user.id, token_balance=user.token_balance)


@router.get("/tokens/transactions", response_model=list[TokenTransactionOut],
            summary="Your token transaction history (append-only ledger)")
def get_transactions(db: Session = Depends(get_db),
                     user: User = Depends(get_current_user),
                     limit: int = Query(50, ge=1, le=100),
                     offset: int = Query(0, ge=0)) -> list[TokenTransactionOut]:
    rows = token_service.list_transactions(db, user.id, limit=limit, offset=offset)
    return [TokenTransactionOut.model_validate(t) for t in rows]


@router.post("/admin/users/{user_id}/tokens", response_model=TokenTransactionOut,
             summary="Admin token grant/deduct (moderator; audited via ledger)")
def admin_grant(user_id: uuid.UUID, payload: AdminTokenGrant,
                db: Session = Depends(get_db),
                mod: User = Depends(require_role("moderator"))) -> TokenTransactionOut:
    kind = TokenKind.admin_grant if payload.amount > 0 else TokenKind.admin_deduct
    tx = token_service.grant(db, user_id, payload.amount, kind,
                             note=payload.note, created_by=mod.id)
    db.commit()
    db.refresh(tx)
    return TokenTransactionOut.model_validate(tx)
