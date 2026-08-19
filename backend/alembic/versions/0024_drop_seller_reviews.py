"""drop seller_reviews — the table the docs claimed was already dropped

Seller trust ratings were built and verified in M2, then withdrawn by owner
decision on 2026-07-28: bluntly.ph is an affiliate-review platform, not a
seller directory. The frontend, API and SQLAlchemy model were removed at the
time (cf7afbc, 8936dda, 9366a5b).

The migration was not. Three documents — MILESTONES.md, FRONTEND_MILESTONES.md
and schema.md — have since stated that `0021_drop_seller_reviews` exists and is
"written, not yet applied". No such file was ever written; `0021` is
`review_comments`. The table stayed in production carrying 10 rows.

Verified before writing this, because "the docs say so" is not evidence:

* no runtime code reads or writes the table — the model is already gone, and
  the only surviving references are a `moderation_target_type` enum value, a
  stale comment, and generated API types
* no foreign key anywhere points at it
* all 10 rows are fixtures: zero were authored by a non-`@example.com` account
* the withdrawal decision is recorded in `docs/MILESTONES.md`

The rows were exported outside the repository before this ran.

`moderation_target_type.seller_review` is deliberately NOT removed. Dropping a
value from a PostgreSQL enum is genuinely destructive and cannot be done in
place, and `moderation_logs` may hold historical rows referring to it. An
unused enum value costs nothing; rewriting history to tidy it would.

Rollout: contracting, but backward compatible in practice — the deployed
application has had no reference to this table since 2026-07-28, so no running
code can break. Deploy first regardless, then apply, per docs/ENVIRONMENTS.md.

Revision ID: 0024_drop_seller_reviews
Revises: 0023_receipt_object_key
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0024_drop_seller_reviews"
down_revision = "0023_receipt_object_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # RLS policies and the table's own indexes go with it.
    op.execute("DROP TABLE IF EXISTS seller_reviews CASCADE")

    # users.seller_trust_score / seller_aggregates were the denormalized
    # mirrors of this table (M2 slice 4). With the source gone they can only
    # ever hold stale numbers, and a stale trust score is worse than none.
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS seller_trust_score")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS seller_aggregates")


def downgrade() -> None:
    """Recreates the shape, not the data.

    The 10 rows were fixtures and were archived outside the repository; a
    downgrade that silently produced an empty table pretending to be the old
    one would be worse than an obvious empty one.
    """
    op.create_table(
        "seller_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("seller_review_id", sa.String(32)),
        sa.Column("seller_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("product_id", UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("accuracy", sa.Boolean()),
        sa.Column("order_completeness", sa.Boolean()),
        sa.Column("customer_service", sa.SmallInteger()),
        sa.Column("packaging_quality", sa.SmallInteger()),
        sa.Column("overall_rating", sa.SmallInteger()),
        sa.Column("would_recommend", sa.Boolean()),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.add_column("users", sa.Column("seller_trust_score", sa.Numeric(6, 5)))
    op.add_column("users", sa.Column("seller_aggregates", JSONB()))
