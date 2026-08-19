"""Alembic environment — targets app.models metadata, URL from app settings."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

# Resolve the target BEFORE importing settings: pydantic-settings reads its
# env_file at import time, so a later os.environ change would not be seen.
#
# This guard exists because of a near-miss. `alembic upgrade head` reads the
# repo-root .env, which is production - so an operator intending to migrate the
# test database silently migrated production instead. pytest and the scripts
# were already guarded; alembic was the remaining door, and it is the one that
# applies schema changes.
#
# Choose the target explicitly:
#   alembic -x test=1 upgrade head              -> the test project
#   alembic -x allow_production=1 upgrade head  -> production, deliberately
from app.core.env_guard import (  # noqa: E402
    ProductionTargetError,
    describe_target,
    load_test_env,
    require_non_production,
)

_x = context.get_x_argument(as_dictionary=True)
if _x.get("test"):
    load_test_env()

_allow_production = bool(_x.get("allow_production"))
print(f"[alembic] target -> {describe_target()}")
try:
    require_non_production("alembic", allow_production=_allow_production)
except ProductionTargetError as _exc:
    raise SystemExit(str(_exc)) from None

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402

# Import the models package so every table registers on Base.metadata.
import app.models  # noqa: F401,E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Indexes Alembic autogenerate structurally CANNOT express, so it reports them as
# spurious drops on every run and drowns real drift in noise. Each is created and
# dropped by explicit raw SQL in a migration:
#   * partial indexes (CREATE UNIQUE INDEX ... WHERE ...)
#   * the pg_trgm GIN index
#   * an expression index (created_at DESC)
# Excluding them by name is what makes `alembic check` a meaningful CI gate:
# everything NOT in this set must match the models exactly.
_SQL_MANAGED_INDEXES = {
    "uq_token_once",              # partial: earn kinds with a ref_id
    "uq_referral_active",         # partial: one active link per review
    "uq_referral_sub_id_active",  # partial: sub_id unique among active links
    "uq_contract_active",         # partial: one active contract per review
    "uq_payout_user_batch",       # partial: one payout per user per batch
    "ix_reviews_discussion_trgm",  # GIN gin_trgm_ops
    "ix_token_tx_user_created",   # expression: (user_id, created_at DESC)
}


def include_object(obj, name, type_, reflected, compare_to):  # noqa: ARG001
    if type_ == "index" and name in _SQL_MANAGED_INDEXES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.effective_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    # Use effective URL (Supabase when USE_SUPABASE=true) + SSL/pooler connect args.
    connectable = create_engine(
        settings.effective_database_url,
        poolclass=pool.NullPool,
        connect_args=settings.db_connect_args,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
