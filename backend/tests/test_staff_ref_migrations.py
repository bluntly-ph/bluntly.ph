"""Static and live invariants for the staff-reference migration chain."""

from __future__ import annotations

import pathlib

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import make_user, requires_db

VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _source(name: str) -> str:
    return next(VERSIONS.glob(f"{name}*.py")).read_text(encoding="utf-8")


def test_expand_backfill_tighten_and_enum_steps_are_separate():
    expand = _source("0038_staff_ref_and_super_admin")
    tighten = _source("0039_staff_ref_not_null")
    audit = _source("0040_role_admin_audit_enum")

    assert 'down_revision = "0037_cron_lease"' in expand
    assert 'down_revision = "0038_staff_ref_and_super_admin"' in tighten
    assert 'down_revision = "0039_staff_ref_not_null"' in audit
    assert "row_number() OVER (ORDER BY created_at, id)" in expand
    assert "CREATE SEQUENCE" in expand and "setval" in expand
    assert "create_index" in expand and "unique=True" in expand
    assert "users_staff_ref_is_immutable" in expand
    assert "ck_users_super_admin_is_moderator" in expand
    assert 'alter_column("users", "staff_ref", nullable=False' not in expand
    assert "nullable=False" in tighten and "UPDATE users" not in tighten
    assert "ALTER TYPE moderation_action ADD VALUE" in audit
    assert "add_column" not in audit and "alter_column" not in audit


@requires_db
def test_live_staff_reference_is_generated_unique_indexed_and_immutable(db):
    first = make_user(db)
    second = make_user(db)
    db.flush()
    assert first.staff_ref.startswith("USR-")
    assert second.staff_ref.startswith("USR-")
    assert first.staff_ref != second.staff_ref

    indexes = inspect(db.get_bind()).get_indexes("users")
    staff_index = next(i for i in indexes if i["name"] == "ix_users_staff_ref")
    assert staff_index["unique"] is True

    with pytest.raises(IntegrityError):
        db.execute(
            text("UPDATE users SET staff_ref = :new WHERE id = :id"),
            {"new": "USR-999999999999", "id": first.id},
        )
        db.flush()
    db.rollback()


@requires_db
def test_live_staff_reference_is_not_null_and_has_database_default(db):
    column = next(
        c for c in inspect(db.get_bind()).get_columns("users") if c["name"] == "staff_ref")
    assert column["nullable"] is False
    assert "users_staff_ref_seq" in str(column["default"])
