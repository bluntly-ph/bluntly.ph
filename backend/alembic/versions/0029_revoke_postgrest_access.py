"""close the PostgREST surface: revoke anon/authenticated from the public schema

CRITICAL, found 2026-08-20 and confirmed against production. An anonymous
caller holding the publishable key - which is public by design, and is handed
out by Supabase to anyone who asks for it - could read table rows directly over
PostgREST, bypassing the API and every serializer in it:

    users            email, password_hash, payout_account, token_balance
    reviews          receipt_key, affiliate_link
    review_versions, referral_links, questions, products   (whole rows)

The policies were not missing. They were `USING (true)` under names like
`users_select_public`, written as though the table were the public view of the
entity. But RLS is *row*-level: `true` grants every **column**, and these
tables carry, in columns the API never serves, exactly what the API is careful
never to serve. `reviews.receipt_key` is the storage path of a proof-of-purchase
document, which the receipt work went to some length to keep unreachable.

Grants, not policies, are the right instrument. A policy cannot express "these
columns but not those", and rewriting fourteen policies to chase a moving set
of columns would leave the same trap for the next column somebody adds.

**Nothing in this application uses PostgREST.** The API connects as `postgres`
via SQLAlchemy and storage uses the service-role key; `get_publishable_client()`
exists in `app/core/supabase_client.py` and is never called. So the entire
REST surface is attack surface and nothing else, and closing it costs nothing.

Safe in any deploy order: it removes privileges from two roles the application
never authenticates as.

Revision ID: 0029_revoke_postgrest_access
Revises: 0028_rate_limit_counters
"""
from __future__ import annotations

from alembic import op

revision = "0029_revoke_postgrest_access"
down_revision = "0028_rate_limit_counters"
branch_labels = None
depends_on = None

ROLES = "anon, authenticated"


def upgrade() -> None:
    # Existing objects.
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {ROLES}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {ROLES}")
    op.execute(f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM {ROLES}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLES}")

    # And the future ones. Supabase ships a default-privileges rule that grants
    # every new table to these roles, so without this the hole reopens the next
    # time a migration adds a table - which is the failure mode that put
    # `receipt_key` behind a `USING (true)` policy in the first place.
    for owner in ("postgres", "supabase_admin"):
        op.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public "
                   f"REVOKE ALL ON TABLES FROM {ROLES}")
        op.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public "
                   f"REVOKE ALL ON SEQUENCES FROM {ROLES}")
        op.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public "
                   f"REVOKE ALL ON FUNCTIONS FROM {ROLES}")


def downgrade() -> None:
    """Deliberately not reversible.

    The downgrade would be to re-expose `users.password_hash` and
    `reviews.receipt_key` to anonymous callers. If PostgREST is ever genuinely
    wanted, grant it deliberately and per column - never by restoring this.
    """
