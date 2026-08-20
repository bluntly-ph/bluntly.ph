"""a durable counter for rate limiting, so the limiter does not depend on Redis

Audit finding, proven against production on 2026-08-20: fourteen consecutive
failed logins from one address all returned 401 and none returned 429, against
a configured limit of ten per minute. Login, register, OTP request, OTP verify,
voting, reporting and commenting were all unthrottled.

`app/core/rate_limit.py` fails open by design - a Redis outage must not take
down auth - and `REDIS_URL` appears nowhere in the repository, so the default
`redis://localhost:6379/0` is what the deployed function tries to reach. Every
call raised, was logged at info, and was allowed. `config.production_issues()`
does check for exactly this, but that check only runs when `APP_ENV=production`,
and whatever the deployed value is, the app plainly started.

Failing open was the right call for availability and the wrong one to leave as
the only story. This adds a second backing store so the control survives Redis
being absent, using the database the platform already depends on rather than
introducing another piece of paid infrastructure for a counter.

Purely additive: a new table nothing yet reads. Safe in any deploy order.

Revision ID: 0028_rate_limit_counters
Revises: 0027_normalize_product_categories
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_rate_limit_counters"
down_revision = "0027_normalize_product_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_counters",
        # "rl:<bucket>:<client>" - the same key shape the Redis path uses, so
        # the two stores stay describable as one thing.
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("count >= 0", name="ck_rate_limit_count_non_negative"),
    )
    # Supports the opportunistic prune of windows that closed long ago. Without
    # it that sweep is a sequential scan on a table with a row per client IP.
    op.create_index("ix_rate_limit_counters_window_start",
                    "rate_limit_counters", ["window_start"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_counters_window_start",
                  table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
