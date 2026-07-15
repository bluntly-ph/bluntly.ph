"""Token ledger service (M2 slice 7).

`grant` is the ONLY way a balance changes: row-locked, ledger + mirror updated in
the caller's transaction, idempotent for earn kinds via the uq_token_once partial
unique index. Negative amounts deduct; a balance can never go below zero.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import TokenKind
from app.models.token import TokenTransaction
from app.models.user import User


def grant(db: Session, user_id: uuid.UUID, amount: int, kind: TokenKind,
          ref_type: str | None = None, ref_id: uuid.UUID | None = None,
          note: str | None = None, created_by: uuid.UUID | None = None
          ) -> TokenTransaction | None:
    """Apply a signed token amount. Does NOT commit (caller owns the transaction).

    Returns the ledger row, or None when an earn kind already awarded for this
    ref (idempotent no-op via uq_token_once).
    """
    if amount == 0:
        raise AppError("Token amount must be non-zero.", code="token_amount_zero",
                       status_code=422, title="Invalid token amount")

    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise AppError("User not found.", code="user_not_found",
                       status_code=404, title="Resource not found")
    new_balance = user.token_balance + amount
    if new_balance < 0:
        raise AppError("Insufficient token balance.", code="insufficient_tokens",
                       status_code=409, title="Conflicting state")

    tx = TokenTransaction(user_id=user_id, amount=amount, balance_after=new_balance,
                          kind=kind, ref_type=ref_type, ref_id=ref_id, note=note,
                          created_by=created_by)
    try:
        # Savepoint so a duplicate earn can't poison the caller's transaction.
        # add() must happen INSIDE it — the savepoint rollback then expunges the
        # pending row instead of retrying it on the next flush.
        with db.begin_nested():
            db.add(tx)
            db.flush()
    except IntegrityError:
        return None  # already awarded for this (user, kind, ref) — idempotent no-op
    user.token_balance = new_balance
    return tx


def award_review_published(db: Session, review_author_id: uuid.UUID,
                           review_id: uuid.UUID) -> None:
    """Publish hook (first publish only — uq_token_once absorbs re-publishes)."""
    from app.core.config import settings

    if settings.tokens_on_review_published > 0:
        grant(db, review_author_id, settings.tokens_on_review_published,
              TokenKind.earn_review_published, ref_type="review", ref_id=review_id)


def list_transactions(db: Session, user_id: uuid.UUID,
                      limit: int = 50, offset: int = 0) -> list[TokenTransaction]:
    return list(db.scalars(
        select(TokenTransaction).where(TokenTransaction.user_id == user_id)
        .order_by(TokenTransaction.created_at.desc(), TokenTransaction.id.desc())
        .limit(min(limit, 100)).offset(offset)))
