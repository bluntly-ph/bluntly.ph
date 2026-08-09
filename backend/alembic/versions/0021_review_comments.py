"""review_comments + review_comment_votes — discussion under a review (BUG-014)

The review detail page had no comment surface at all. This adds the two tables
behind it: the comments themselves, threaded one level deep via a self-FK, and
equal-weight votes on them.

`vote_direction` already exists (0002); reference it rather than re-CREATE TYPE.

Revision ID: 0021_review_comments
Revises: 0020_affiliate_postbacks
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0021_review_comments"
down_revision = "0020_affiliate_postbacks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("review_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        # SET NULL, like reviews.author_id: deleting an account must not erase a
        # conversation other people took part in.
        sa.Column("author_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        # Self-FK for replies. CASCADE: a deleted thread root takes its replies.
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("review_comments.id", ondelete="CASCADE")),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("helpful_votes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unhelpful_votes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_removed", sa.Boolean(), nullable=False, server_default="false"),
    )
    # The read path is always "every comment on this review, oldest first".
    op.create_index("ix_review_comments_review_created", "review_comments",
                    ["review_id", "created_at"])
    op.create_index("ix_review_comments_parent_id", "review_comments", ["parent_id"])

    op.create_table(
        "review_comment_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("comment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("review_comments.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("voter_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vote", postgresql.ENUM(name="vote_direction", create_type=False),
                  nullable=False),
        sa.UniqueConstraint("comment_id", "voter_id",
                            name="uq_review_comment_vote_once"),
    )
    op.create_index("ix_review_comment_votes_comment_id", "review_comment_votes",
                    ["comment_id"])

    # Dormant defence in depth, matching every other table (0002_rls_policies).
    op.execute("ALTER TABLE public.review_comments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.review_comment_votes ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_review_comment_votes_comment_id",
                  table_name="review_comment_votes")
    op.drop_table("review_comment_votes")
    op.drop_index("ix_review_comments_parent_id", table_name="review_comments")
    op.drop_index("ix_review_comments_review_created", table_name="review_comments")
    op.drop_table("review_comments")
