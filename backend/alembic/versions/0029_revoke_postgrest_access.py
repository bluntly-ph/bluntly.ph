"""close the PostgREST surface: revoke anon/authenticated from the public schema

CRITICAL, found 2026-08-20 and confirmed against production. An anonymous
caller holding the publishable key - which is public by design, and which
Supabase hands to anyone who asks - could read table rows directly over
PostgREST, bypassing the API and every serializer in it.

**17 of the 28 tables** carry a SELECT policy of `USING (true)`, which returns
every row and every column to `anon`:

    answers            earn_eligible_votes  price_history     referral_links
    badges             membership_tiers     product_platforms request_upvotes
    products           questions            review_contracts  review_requests
    review_versions    review_votes         reviews           user_badges
    users

Between them that includes `users.email`, `users.password_hash`,
`users.payout_account`, `reviews.receipt_key` - the storage path of a
proof-of-purchase document - and `reviews.affiliate_link`, plus the identity
behind every vote and price submission.

The policies were not missing. They were written as though the table were the
public view of the entity, under names like `users_select_public`. But RLS is
*row*-level: `true` grants every **column**, and these tables carry, in columns
the API never serves, exactly what the API is careful never to serve.

What was NOT exposed, because these 11 tables have no SELECT policy at all and
RLS therefore denies by default:

    affiliate_postbacks  alembic_version  commissions   email_otps
    honesty_fund_distributions            moderation_logs
    payouts              review_comment_votes           review_comments
    sessions             token_transactions

That is the mitigating half of the finding and it is not luck about which
tables matter most: session records and OTP codes - the two that would turn a
read into an account takeover - were never reachable.

Writes were not possible either. Every INSERT/UPDATE/DELETE policy tests
`= auth.uid()`, which is NULL for an anonymous caller, so RLS refused them -
even though the grant itself is `arwdDxtm`, i.e. ALL. TRUNCATE is the exception
that is *not* subject to RLS, but PostgREST has no verb that emits one, so it
stayed latent. This migration removes the grant regardless.

**Grants, not policies, are the right instrument.** A policy cannot express
"these columns but not those", and rewriting seventeen policies to chase a
moving set of columns would leave the same trap for the next column added.

Note on schema USAGE: `public` is granted to the PUBLIC pseudo-role and every
role inherits from it, so revoking USAGE from `anon` by name does not take away
what PUBLIC gives. It is revoked here anyway to clear any direct grant, but it
is not the control - the table privileges are. USAGE only permits name
resolution, and after this there is nothing left to resolve to.

**Nothing in this application uses PostgREST.** The API connects as `postgres`
via SQLAlchemy and storage uses the service-role key; `get_publishable_client()`
exists in `app/core/supabase_client.py` and is never called. There are no
views, no materialized views, no sequences and no SECURITY DEFINER functions in
`public` - the only functions there are pg_trgm's, so there is no RPC surface
either. The entire REST surface is attack surface and nothing else.

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
    #
    # `postgres` is the role migrations run as, so it can always alter its own
    # defaults. This half must succeed.
    for what in ("TABLES", "SEQUENCES", "FUNCTIONS"):
        op.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
                   f"REVOKE ALL ON {what} FROM {ROLES}")

    # `supabase_admin` is a different story: only that role (or a superuser) may
    # change its defaults, and Supabase does not grant the project's `postgres`
    # role that power. It answers
    #   InsufficientPrivilege: permission denied to change default privileges
    #
    # Attempted anyway, because on any deployment where it IS permitted this is
    # the difference between the hole staying shut and reopening. But a refusal
    # must not fail the migration: it would make a fresh database unable to
    # reach head on Supabase at all, which is exactly what it did - this
    # migration is why the isolated test project could not be built.
    #
    # The residual risk is real and already recorded: a table created outside
    # our migrations could arrive readable by `anon`. Two invariants in
    # `check_invariants` fail the moment any table becomes readable by `anon`
    # or `authenticated`, so this degrades to detection rather than prevention
    # instead of degrading to silence.
    for what in ("TABLES", "SEQUENCES", "FUNCTIONS"):
        op.execute(f"""
            DO $$
            BEGIN
                ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
                    REVOKE ALL ON {what} FROM {ROLES};
            EXCEPTION WHEN insufficient_privilege THEN
                RAISE NOTICE 'skipped: cannot alter supabase_admin default '
                             'privileges on {what}; check_invariants covers it';
            END $$;
        """)


def downgrade() -> None:
    """Deliberately not reversible.

    The downgrade would be to re-expose `users.password_hash` and
    `reviews.receipt_key` to anonymous callers. If PostgREST is ever genuinely
    wanted, grant it deliberately and per column - never by restoring this.
    """
