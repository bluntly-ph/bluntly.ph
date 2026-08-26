"""Do the ORM models and the migrated schema actually agree?

Narrow on purpose. This is not a schema-diff framework and must not become
one — a check that reports fifty harmless differences is a check nobody reads.
It asserts exactly one property, the one that has already caused an incident:

    the database requires a column and supplies a default,
    but the model does not declare that default

In that shape SQLAlchemy does not know the database will fill the column, so it
writes an explicit `column = NULL` into every INSERT and the default never
applies. `affiliate_postbacks.received_at` sat like that from migration 0020
until the lifecycle importer became the first code to insert a postback through
the ORM, and then every one of its tests failed on a not-null violation 74
minutes into CI.

Autoincrement primary keys are exempt: SQLAlchemy handles them specially,
omitting them from the INSERT and reading back the generated value.
"""

from __future__ import annotations

from sqlalchemy import text

import app.models  # noqa: F401 — registers every model on the metadata
from app.db.base import Base
from tests.conftest import requires_db


@requires_db
def test_no_model_overrides_a_database_default_with_null(db):
    """Every NOT NULL column with a database default must be declared as such.

    The failure mode is silent until something inserts through the ORM, which
    is why this is asserted rather than left to review.
    """
    rows = db.execute(text("""
        SELECT table_name, column_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
    """)).all()
    live = {
        (t, c): (nullable == "YES", default)
        for t, c, nullable, default in rows
    }

    drift: list[str] = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            found = live.get((table.name, column.name))
            if found is None:
                # The model has a column the database does not. That is a
                # missing migration rather than this check's subject, and the
                # migration-safety script already covers it.
                continue
            db_nullable, db_default = found
            if db_nullable or db_default is None:
                continue
            if column.server_default is not None or column.default is not None:
                continue
            if column.primary_key and column.autoincrement:
                continue
            drift.append(
                f"{table.name}.{column.name}: database is NOT NULL DEFAULT "
                f"{str(db_default)[:32]!r}, but the model declares no default — "
                f"SQLAlchemy will INSERT an explicit NULL and the default will "
                f"never apply"
            )

    assert not drift, "model/schema drift:\n  " + "\n  ".join(drift)


@requires_db
def test_no_model_claims_a_column_is_optional_that_the_database_requires(db):
    """A model that thinks a required column is optional will let code omit it
    and fail at flush time instead of at review time.

    Columns with ANY default are excluded — a database default or a Python-side
    one both mean a value always arrives. `users.username` is the worked
    example: the database requires it, the model types it optional, and a
    `default=lambda` supplies a collision-proof handle for every code path that
    does not go through `allocate_username`. That is deliberate and documented
    at the column, and a check that flagged it would be the noise this file
    exists to avoid.
    """
    rows = db.execute(text("""
        SELECT table_name, column_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
    """)).all()
    live = {
        (t, c): (nullable == "YES", default)
        for t, c, nullable, default in rows
    }

    wrong: list[str] = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            found = live.get((table.name, column.name))
            if found is None:
                continue
            db_nullable, db_default = found
            if db_nullable or db_default is not None:
                continue
            if column.default is not None or column.server_default is not None:
                continue
            if column.nullable:
                wrong.append(
                    f"{table.name}.{column.name}: database is NOT NULL with no "
                    f"default, but the model says nullable"
                )

    assert not wrong, "model says optional, database says required:\n  " + "\n  ".join(wrong)
