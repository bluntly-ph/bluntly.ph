"""Session PII retention correctness (Architecture §4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.pii import due_actions, hash_ip, retention_deadlines

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def test_deadlines_are_30_90_90():
    d = retention_deadlines(BASE)
    assert d["ip_hash_at"] == BASE + timedelta(days=30)
    assert d["ip_delete_at"] == BASE + timedelta(days=90)
    assert d["ua_purge_at"] == BASE + timedelta(days=90)


def test_nothing_due_before_30_days():
    actions = due_actions(clicked_at=BASE, now=BASE + timedelta(days=29),
                          has_user_agent=True, has_raw_ip=True, has_ip_hash=False)
    assert actions == set()


def test_ip_hash_due_at_30_days():
    actions = due_actions(clicked_at=BASE, now=BASE + timedelta(days=30),
                          has_user_agent=True, has_raw_ip=True, has_ip_hash=False)
    assert actions == {"hash_ip"}


def test_full_purge_at_90_days():
    actions = due_actions(clicked_at=BASE, now=BASE + timedelta(days=90),
                          has_user_agent=True, has_raw_ip=False, has_ip_hash=True)
    assert actions == {"delete_ip_hash", "purge_ua"}


def test_hash_ip_is_deterministic_and_irreversible():
    h1 = hash_ip("203.0.113.7", salt="s")
    h2 = hash_ip("203.0.113.7", salt="s")
    assert h1 == h2 and len(h1) == 64 and "203.0.113.7" not in h1
    assert hash_ip("203.0.113.7", salt="other") != h1
