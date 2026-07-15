"""Sessions PII retention sweep (M2 slice 8; Architecture §4).

Bulk SQL (not per-row Python): the schedule deadlines were precomputed on insert
(`ip_hash_at` / `ip_delete_at` / `ua_purge_at`), so each step is one UPDATE.
The 30-day hash uses Postgres' built-in sha256 over exactly the same
`{salt}:{ip}` string as `services.pii.hash_ip`, so the two stay interchangeable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


def run_retention_sweep(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Apply all due retention actions; returns {"hashed": n, "purged": n}."""
    now = now or datetime.now(UTC)
    salt = settings.pii_hash_salt

    # >= 30d: replace the raw IP with a salted hash (matches pii.hash_ip).
    hashed = db.execute(
        text("""
            UPDATE sessions
            SET ip_hash = encode(sha256(convert_to(:salt || ':' || host(ip_address),
                                                   'UTF8')), 'hex'),
                ip_address = NULL
            WHERE ip_hash_at <= :now AND ip_address IS NOT NULL
        """),
        {"salt": salt, "now": now},
    ).rowcount

    # >= 90d: delete the hash too, and purge the user agent.
    purged_ip = db.execute(
        text("""
            UPDATE sessions
            SET ip_hash = NULL, ip_address = NULL
            WHERE ip_delete_at <= :now
              AND (ip_hash IS NOT NULL OR ip_address IS NOT NULL)
        """),
        {"now": now},
    ).rowcount
    purged_ua = db.execute(
        text("""
            UPDATE sessions
            SET user_agent = NULL
            WHERE ua_purge_at <= :now AND user_agent IS NOT NULL
        """),
        {"now": now},
    ).rowcount

    db.commit()
    return {"hashed": hashed, "purged": purged_ip + purged_ua}
