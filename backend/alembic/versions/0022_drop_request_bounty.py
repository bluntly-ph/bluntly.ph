"""drop review_requests.bounty — the token economy is retired

The request board was the last thing still spending tokens: posting a request
escrowed a bounty, cancelling or expiring refunded it, and fulfilling paid it
out plus a platform-minted top-up. Tokens were retired in favour of the PHP
revenue share (see lib/dashboard.ts), which left the board charging a currency
nothing else recognised — and a reviewer discovering only on submit that they
could not afford to ask a question (BUG-025).

A request is now a free demand signal: you ask, others up-vote to say they want
it too, and whoever writes the review earns through the ordinary revenue share.

The ledger is untouched. `token_transactions` is append-only and keeps every
historical escrow, refund and reward exactly as it happened; the TokenKind enum
keeps its request_* members so those rows stay readable. Outstanding escrows on
still-open requests are deliberately *not* refunded here: the currency has no
value to return, and minting refunds for it would write new history to undo old
history that was true when it was written.

Revision ID: 0022_drop_request_bounty
Revises: 0021_review_comments
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0022_drop_request_bounty"
down_revision = "0021_review_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("review_requests", "bounty")


def downgrade() -> None:
    # Restored with a server default so existing rows are valid without having
    # to guess what any individual request once escrowed — that information is
    # in the ledger, not recoverable from this table.
    op.add_column(
        "review_requests",
        sa.Column("bounty", sa.Integer(), nullable=False, server_default="0"),
    )
