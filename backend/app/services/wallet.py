"""Wallet balance changes, expressed as one statement.

    user.wallet_balance = user.wallet_balance + x

reads, adds and writes in three steps. Two concurrent adjustments to one wallet
both read the same starting balance, and the second write silently discards the
first. Every path that moves money did it this way: the payout reserve and its
two refunds, the commission split, a contract buyout, and an Honesty Fund
distribution.

Three of those are credits, so the lost update costs a real person real money
they earned, and nothing anywhere reports it - the balance is simply lower than
the sum of its inflows. It is not a race that needs an attacker either: the
payout scheduler and a moderator approving a commission touch the same wallets
by design.

As one UPDATE the addition happens under the row lock Postgres already takes
for the write, so concurrent adjustments compose. `ck_user_wallet_non_negative`
(migration 0026) then turns an over-debit into an IntegrityError rather than a
negative balance.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.user import User


def adjust(db: Session, user_id: uuid.UUID, delta: Decimal) -> None:
    """Move a wallet balance by `delta`. Negative debits, positive credits.

    Does not commit: the caller owns the transaction, because a balance change
    is only ever half of something - a payout row, a commission, a refund - and
    the two must land together or not at all.
    """
    db.execute(update(User)
               .where(User.id == user_id)
               .values(wallet_balance=User.wallet_balance + delta))
