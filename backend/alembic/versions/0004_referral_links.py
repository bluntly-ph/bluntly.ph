"""referral links + publication gate (M2 slice 1)

- reviews.published_at (nullable; backfill existing = created_at)
- referral_links table (link history + audit; one active link per review)
- platform enum += 'amazon'; moderation_action enum += 4 referral/publish actions

Enum ADD VALUE must run outside a transaction (Postgres), so it goes in an
autocommit block. Downgrade drops the table/column; Postgres can't drop enum values
(documented — consistent with prior migrations).

Revision ID: 0004_referral_links
Revises: 0003_rls_alembic_version
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_referral_links"
down_revision = "0003_rls_alembic_version"
branch_labels = None
depends_on = None

referral_link_status = postgresql.ENUM(
    "active", "revoked", name="referral_link_status", create_type=False
)
platform = postgresql.ENUM(name="platform", create_type=False)

_NEW_MODERATION_ACTIONS = (
    "affiliate_link_attach", "affiliate_link_revoke", "publish", "unpublish",
)


def upgrade() -> None:
    # 1. Enum additions — must be outside the migration transaction.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE platform ADD VALUE IF NOT EXISTS 'amazon'")
        for value in _NEW_MODERATION_ACTIONS:
            op.execute(f"ALTER TYPE moderation_action ADD VALUE IF NOT EXISTS '{value}'")

    # 2. Publication gate column + backfill (existing reviews stay live).
    op.add_column("reviews", sa.Column("published_at", sa.DateTime(timezone=True)))
    op.create_index("ix_reviews_published_at", "reviews", ["published_at"])
    op.execute("UPDATE reviews SET published_at = created_at WHERE published_at IS NULL")

    # 3. referral_links table.
    referral_link_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "referral_links",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("review_id", sa.UUID(), nullable=False),
        sa.Column("platform", platform, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", referral_link_status, server_default="active", nullable=False),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_referral_links_review_id", "referral_links", ["review_id"])
    # Exactly one active link per review.
    op.execute(
        "CREATE UNIQUE INDEX uq_referral_active ON referral_links (review_id) "
        "WHERE status = 'active'"
    )
    # RLS (defense-in-depth; consistent with the rest of the schema).
    op.execute("ALTER TABLE referral_links ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY referral_links_select_public ON referral_links "
               "FOR SELECT USING (true)")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS referral_links_select_public ON referral_links")
    op.drop_index("ix_referral_links_review_id", table_name="referral_links")
    op.execute("DROP INDEX IF EXISTS uq_referral_active")
    op.drop_table("referral_links")
    referral_link_status.drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_reviews_published_at", table_name="reviews")
    op.drop_column("reviews", "published_at")
    # Note: Postgres cannot DROP enum values, so 'amazon' and the new
    # moderation_action values remain after downgrade (harmless).
