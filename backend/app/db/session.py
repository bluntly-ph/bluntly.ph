"""Engine and session management."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# The APP serves from `runtime_database_url` (Supabase TRANSACTION pooler), not
# the session pooler Alembic uses. Measured 2026-07-16: the session pooler caps
# at 4 concurrent clients (EMAXCONNSESSION) — nowhere near enough for 2 workers
# plus Celery, and it 500s the API under load. See config.runtime_database_url.
engine = create_engine(
    settings.runtime_database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    future=True,
    connect_args=settings.runtime_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                            expire_on_commit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a transactional session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
