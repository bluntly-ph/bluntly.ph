"""Session PII retention logic (Architecture §4).

Pure functions so the retention rules are unit-testable now, even though the
Celery job that applies them across the table is M2. Schedule:
  * IP hashed at 30 days (raw IP replaced by a salted hash), deleted at 90 days.
  * User agent purged at 90 days.
Deadlines are precomputed on session insert; the sweep then compares against now.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from app.core.constants import (
    SESSION_IP_DELETE_AFTER_DAYS,
    SESSION_IP_HASH_AFTER_DAYS,
    SESSION_UA_PURGE_AFTER_DAYS,
)


def retention_deadlines(clicked_at: datetime) -> dict[str, datetime]:
    """Precompute the three retention deadlines for a session."""
    return {
        "ip_hash_at": clicked_at + timedelta(days=SESSION_IP_HASH_AFTER_DAYS),
        "ip_delete_at": clicked_at + timedelta(days=SESSION_IP_DELETE_AFTER_DAYS),
        "ua_purge_at": clicked_at + timedelta(days=SESSION_UA_PURGE_AFTER_DAYS),
    }


def hash_ip(ip: str, salt: str) -> str:
    """Salted SHA-256 of an IP for the 30-day hash step (irreversible)."""
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


def due_actions(
    *,
    clicked_at: datetime,
    now: datetime,
    has_user_agent: bool,
    has_raw_ip: bool,
    has_ip_hash: bool,
) -> set[str]:
    """Return the retention actions currently due for one session.

    Actions: "hash_ip" (>=30d, raw IP still present), "delete_ip_hash" (>=90d),
    "purge_ua" (>=90d, UA still present).
    """
    deadlines = retention_deadlines(clicked_at)
    actions: set[str] = set()
    if has_raw_ip and now >= deadlines["ip_hash_at"]:
        actions.add("hash_ip")
    if now >= deadlines["ip_delete_at"] and (has_ip_hash or has_raw_ip):
        actions.add("delete_ip_hash")
    if has_user_agent and now >= deadlines["ua_purge_at"]:
        actions.add("purge_ua")
    return actions
