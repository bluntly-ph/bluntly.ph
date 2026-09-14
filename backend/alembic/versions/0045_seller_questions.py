"""questions asked of a store, and answers from its claimed owner (FR-4, FR-5)

The owner's seller page draws a Questions tab where buyers ask the store and
the store replies under its own name with its Claimed Profile mark. Questions
were product-scoped only (`product_id NOT NULL`), so:

* `questions.product_id` becomes nullable and `questions.seller_id` is added,
  with a CHECK that at least one is set. The schema requires exactly one.
* `answers.is_seller_answer` records that the store's moderator-approved owner
  wrote the answer, as the claim stood at that moment.

Expanding and safe before the code is deployed: the running build never writes
a NULL `product_id`, and ignores the new columns.

The downgrade is destructive for store questions — a `product_id NOT NULL`
column cannot hold them — and deletes them before restoring the constraint.

Revision ID: 0045_seller_questions
Revises: 0044_price_moderation
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0045_seller_questions"
down_revision = "0044_price_moderation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("questions", "product_id",
                    existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("questions", sa.Column(
        "seller_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("sellers.id", ondelete="CASCADE")))
    op.create_check_constraint("ck_question_subject", "questions",
                               "product_id IS NOT NULL OR seller_id IS NOT NULL")
    op.create_index("ix_questions_seller", "questions", ["seller_id", "created_at"])
    op.add_column("answers", sa.Column(
        "is_seller_answer", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("answers", "is_seller_answer")
    op.drop_index("ix_questions_seller", table_name="questions")
    op.drop_constraint("ck_question_subject", "questions", type_="check")
    op.execute("DELETE FROM questions WHERE product_id IS NULL")
    op.drop_column("questions", "seller_id")
    op.alter_column("questions", "product_id",
                    existing_type=postgresql.UUID(as_uuid=True), nullable=False)
