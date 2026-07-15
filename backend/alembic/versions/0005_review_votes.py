"""review_votes — equal-weight community visibility votes (M2 slice 2)

- review_votes table: one vote per (review, voter); upsert changes direction.
- Reuses the existing vote_direction enum (no enum changes needed).
- RLS enabled with a public SELECT policy (consistent with existing style).

Revision ID: 0005_review_votes
Revises: 0004_referral_links
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_review_votes"
down_revision = "0004_referral_links"
branch_labels = None
depends_on = None

vote_direction = postgresql.ENUM(name="vote_direction", create_type=False)


def upgrade() -> None:
    op.create_table(
        "review_votes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("review_id", sa.UUID(), nullable=False),
        sa.Column("voter_id", sa.UUID(), nullable=False),
        sa.Column("vote", vote_direction, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["voter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", "voter_id", name="uq_review_vote_once"),
    )
    op.create_index("ix_review_votes_review_id", "review_votes", ["review_id"])
    op.execute("ALTER TABLE review_votes ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY review_votes_select_public ON review_votes "
               "FOR SELECT USING (true)")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS review_votes_select_public ON review_votes")
    op.drop_index("ix_review_votes_review_id", table_name="review_votes")
    op.drop_table("review_votes")
