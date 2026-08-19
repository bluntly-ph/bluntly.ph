"""reviews.receipt_url -> reviews.receipt_key (private object key)

A receipt is proof of purchase: it carries the buyer's name, address, order
number and prices, and the PRD scopes it to moderator evaluation of the
earn_eligible gate. Storing a permanent PUBLIC url for it put the
authorization decision in a string instead of in the application - anyone
holding it could fetch the object, bypassing every role check and RLS policy
the API applies to the row.

So the column now holds an opaque object key into the PRIVATE review-receipts
bucket. The API never returns it; access goes through an authorized endpoint
that mints a short-lived signed URL.

Two data fixes travel with the rename:

* Existing values are public URLs. The key is the path after the bucket
  segment, so the backfill is deterministic and needs no network call. Copying
  the underlying storage objects into the private bucket is a separate,
  verified step (scripts/migrate_receipts.py) - this migration only moves the
  pointer.

* review_versions.snapshot embedded receipt_url in every row, and BOTH version
  endpoints are readable by anonymous callers for any published review. That
  was a second, independent leak of the same locator. The key is stripped from
  every historical snapshot and replaced with a boolean, so the edit history
  still records that evidence was attached without saying where it lives.

Revision ID: 0023_receipt_object_key
Revises: 0022_drop_request_bounty
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_receipt_object_key"
down_revision = "0022_drop_request_bounty"
branch_labels = None
depends_on = None

# Everything after "/<bucket>/" is the object key. Kept as SQL so the backfill
# runs in one statement against production rather than row-by-row in Python.
_KEY_FROM_URL = r"""
    NULLIF(
        regexp_replace(
            split_part(receipt_url, '/storage/v1/object/public/', 2),
            '^[^/]+/', ''
        ),
        ''
    )
"""


def upgrade() -> None:
    op.add_column("reviews", sa.Column("receipt_key", sa.Text(), nullable=True))
    op.execute(f"""
        UPDATE reviews
           SET receipt_key = {_KEY_FROM_URL}
         WHERE receipt_url IS NOT NULL
           AND receipt_url LIKE '%/storage/v1/object/public/%'
    """)
    op.drop_column("reviews", "receipt_url")

    # Strip the locator from historical version snapshots, keeping the fact.
    op.execute("""
        UPDATE review_versions
           SET snapshot = (snapshot - 'receipt_url')
                          || jsonb_build_object(
                                 'receipt_present',
                                 COALESCE(snapshot->>'receipt_url', '') <> ''
                             )
         WHERE snapshot ? 'receipt_url'
    """)


def downgrade() -> None:
    op.add_column("reviews", sa.Column("receipt_url", sa.Text(), nullable=True))
    # Deliberately NOT reconstructing the public URL. The objects live in a
    # private bucket now and no public URL would resolve; writing one back
    # would be a lie that reads as working. Re-point by hand if ever needed.
    op.drop_column("reviews", "receipt_key")
    op.execute("""
        UPDATE review_versions
           SET snapshot = snapshot - 'receipt_present'
         WHERE snapshot ? 'receipt_present'
    """)
