"""Engine and session management."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.effective_database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    future=True,
    connect_args=settings.db_connect_args,
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
