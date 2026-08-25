"""aggregate request geography, bucketed by hour

Traffic analytics for the moderator dashboard. Deliberately NOT a row per
request: an unbounded request log is both a storage problem and a privacy
problem, and nothing in the panel needs per-request resolution. One row per
(hour x location) is enough to answer "how much traffic, from roughly where",
and it collapses naturally — a thousand requests from Manila in an hour are one
row with a count of 1000.

There is no IP column, and no user column, on purpose. The edge resolves
location before the request reaches us, so the address never has to enter the
application, and without a user reference this table cannot be joined back to a
person. That is what makes it aggregate analytics rather than user tracking.

`latitude`/`longitude` are the edge's own coarse coordinates for the resolved
city, not a device position. They are stored so the map can place a marker
without shipping a city gazetteer, and are nullable because the edge does not
always resolve them.

Retention is enforced in application code (see request_traffic_service), not
here: 90 days of hourly buckets. The published privacy policy already discloses
"basic device, log, and analytics information" and general retention; a hard
90-day cap on aggregates is stricter than that, so it needs no policy change.

Revision ID: 0032_request_geo_buckets
Revises: 0031_affiliate_canonical
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0032_request_geo_buckets"
down_revision = "0031_affiliate_canonical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "request_geo_buckets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        # Start of the hour this count covers, UTC.
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        # Vercel POP that served the request. Infrastructure, not the visitor.
        sa.Column("pop", sa.String(8), nullable=True),
        sa.Column("latitude", sa.Numeric(8, 4), nullable=True),
        sa.Column("longitude", sa.Numeric(8, 4), nullable=True),
        sa.Column("request_count", sa.BigInteger, nullable=False,
                  server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # The UPSERT target. NULLS NOT DISTINCT matters: most of these columns are
    # nullable, and under the default NULLS DISTINCT two country-only rows
    # would never conflict, so every request would insert a new row and the
    # "aggregate" table would grow exactly like a request log.
    op.execute(
        "CREATE UNIQUE INDEX uq_request_geo_bucket "
        "ON request_geo_buckets (bucket_start, country, region, city, pop) "
        "NULLS NOT DISTINCT"
    )
    # Every read is "the last N hours, ranked", so the time column leads.
    op.create_index("ix_request_geo_bucket_start", "request_geo_buckets",
                    ["bucket_start"])


def downgrade() -> None:
    op.drop_index("ix_request_geo_bucket_start", table_name="request_geo_buckets")
    op.drop_index("uq_request_geo_bucket", table_name="request_geo_buckets")
    op.drop_table("request_geo_buckets")
