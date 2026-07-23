"""Username slugification, allocation, and uniqueness."""

from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.services.username import allocate_username, slugify_username
from tests.conftest import requires_db


@pytest.mark.parametrize("raw,expected", [
    ("Viole Was Here", "viole_was_here"),
    ("  Ana  Cruz  ", "ana_cruz"),
    ("JuanDelaCruz", "juandelacruz"),
    ("a!!!b???c", "a_b_c"),
    ("____x____", "x"),
    ("Ñoño", "nono"),        # NFKD + ascii-fold drops the tilde, not the letter
])
def test_slugify(raw, expected):
    assert slugify_username(raw) == expected


def test_slugify_truncates_to_32():
    assert len(slugify_username("x" * 100)) == 32


def test_slugify_returns_empty_for_unusable_input():
    """Punctuation-only input yields nothing; callers must fall back."""
    assert slugify_username("!!!") == ""


@requires_db
def test_allocate_dedupes_on_collision():
    from app.models.enums import MemberRole, MembershipTier, MemberType
    from app.models.user import User

    db = SessionLocal()
    base = f"collide_{uuid.uuid4().hex[:8]}"
    try:
        first = allocate_username(db, base, "a@example.com", uuid.uuid4())
        assert first == base
        db.add(User(email=f"{uuid.uuid4().hex}@example.com", username=first,
                    role=MemberRole.user, member_type=MemberType.shopper,
                    membership_tier=MembershipTier.standard))
        db.commit()
        second = allocate_username(db, base, "b@example.com", uuid.uuid4())
        assert second == f"{base}2"
    finally:
        db.rollback()
        db.close()


@requires_db
def test_allocate_falls_back_to_email_local_part():
    db = SessionLocal()
    try:
        name = allocate_username(db, None, "Fallback.User@example.com", uuid.uuid4())
        assert name.startswith("fallback_user")
    finally:
        db.close()


@requires_db
def test_allocate_falls_back_when_preferred_is_unusable():
    db = SessionLocal()
    try:
        # "!!!" slugs to "" (too short), so allocation must skip to the email
        # local-part rather than producing an empty handle.
        name = allocate_username(db, "!!!", "usable.name@example.com", uuid.uuid4())
        assert name.startswith("usable_name")
    finally:
        db.close()


@requires_db
def test_every_existing_user_has_a_unique_username():
    """Guards the 0016 backfill: no nulls, no duplicates."""
    from sqlalchemy import text

    db = SessionLocal()
    try:
        total = db.execute(text("SELECT count(*) FROM users")).scalar()
        distinct = db.execute(
            text("SELECT count(DISTINCT lower(username)) FROM users")).scalar()
        nulls = db.execute(
            text("SELECT count(*) FROM users WHERE username IS NULL")).scalar()
        assert nulls == 0
        assert total == distinct
    finally:
        db.close()
