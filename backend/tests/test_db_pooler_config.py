"""Supabase pooler selection (prod-critical).

Measured on the live project 2026-07-16: the Supabase **session** pooler (:5432)
accepts only **4** concurrent clients before
`FATAL: (EMAXCONNSESSION) max clients reached in session mode`; the
**transaction** pooler (:6543) accepted 30+. Serving the API from session mode
therefore 500s under load — an api_smoke concurrency burst produced 7/10 failed
review submits until the app was moved to :6543.

Migrations must STAY on session mode: `ALTER TYPE ... ADD VALUE` runs inside
`autocommit_block()`, which transaction mode cannot provide.
"""

from __future__ import annotations

from sqlalchemy.engine import make_url

from app.core.config import Settings

SESSION_CS = ("postgresql://postgres.ref:pw@aws-0-ap-southeast-1.pooler."
              "supabase.com:5432/postgres")


def _s(**kw) -> Settings:
    return Settings(use_supabase=True,
                    supabase_connection_string_session_pooler=SESSION_CS, **kw)


def test_app_serves_from_the_transaction_pooler():
    """The app must NOT use session mode — it caps at ~4 clients."""
    assert make_url(_s().runtime_database_url).port == 6543


def test_migrations_stay_on_the_session_pooler():
    """Transaction mode cannot run autocommit_block() enum ADD VALUE."""
    assert make_url(_s().effective_database_url).port == 5432


def test_transaction_pooler_disables_prepared_statements():
    """pgbouncer transaction mode requires prepare_threshold=None."""
    args = _s().runtime_connect_args
    assert args["prepare_threshold"] is None
    assert args["sslmode"] == "require"


def test_explicit_transaction_string_wins():
    explicit = ("postgresql://postgres.ref:pw@aws-0-ap-southeast-1.pooler."
                "supabase.com:6543/postgres")
    s = _s(supabase_connection_string_transaction_pooler=explicit)
    assert make_url(s.runtime_database_url).port == 6543


def test_local_is_untouched_by_the_pooler_logic():
    s = Settings(use_supabase=False,
                 database_url="postgresql+psycopg://u:p@localhost:5432/db")
    assert s.runtime_database_url == s.effective_database_url == \
        "postgresql+psycopg://u:p@localhost:5432/db"
    assert s.runtime_connect_args == {}


def test_production_refuses_to_serve_from_the_session_pooler():
    """A production boot pointed at session mode is a hard fail, not a warning."""
    s = Settings(
        app_env="production", use_supabase=True,
        supabase_connection_string_session_pooler=SESSION_CS,
        # Force session mode as the runtime URL.
        supabase_connection_string_transaction_pooler=SESSION_CS,
        jwt_secret="x" * 40, pii_hash_salt="y" * 40,
        cors_origins="https://bluntly.ph")
    issues = " ".join(s.production_issues())
    assert "SESSION pooler" in issues and "6543" in issues
