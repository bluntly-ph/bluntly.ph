"""aggregate review views, bucketed by hour

The dashboard's approved Figma shows "Total Views" per review, and nothing in
the schema tracked it — `reviews` has helpful_votes and wilson_score but no
view count at all. Rather than invent the number, this records it.

Same shape and the same privacy posture as `request_geo_buckets` (0032): one
row per (hour x review), incremented by UPSERT, with NO user column and no IP.
A row here says "this review was opened 40 times in this hour" and cannot say
by whom — which is what keeps it a popularity counter rather than a reading
log.

It is filled by the proxy beacon that already runs on every page request, so a
view costs no extra work: the beacon simply carries the review id when the path
it saw was a review.

Retention matches the traffic buckets (90 days of hourly rows), enforced in
application code. Lifetime totals are NOT derivable from this table after that
window, which is deliberate — a per-review lifetime counter is a different
thing with a different retention argument, and inventing one here would quietly
create a permanent record of reader interest in a table that promises not to
keep one.

Revision ID: 0033_review_view_buckets
Revises: 0032_request_geo_buckets
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0033_review_view_buckets"
down_revision = "0032_request_geo_buckets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_view_buckets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("review_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("view_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    # The UPSERT target. Both columns are NOT NULL here, so the default
    # NULLS DISTINCT behaviour that mattered in 0032 is not a concern.
    op.create_index("uq_review_view_bucket", "review_view_buckets",
                    ["review_id", "bucket_start"], unique=True)
    # Reads are "this author's reviews over the last N days", which lands on
    # the time column after the join.
    op.create_index("ix_review_view_bucket_start", "review_view_buckets",
                    ["bucket_start"])


def downgrade() -> None:
    op.drop_index("ix_review_view_bucket_start", table_name="review_view_buckets")
    op.drop_index("uq_review_view_bucket", table_name="review_view_buckets")
    op.drop_table("review_view_buckets")
