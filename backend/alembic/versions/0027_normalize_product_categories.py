"""normalise product.category onto the canonical slugs

Audit finding. The category vocabulary lived only in the frontend
(`lib/interests.ts`) while `products.category` was an unconstrained
`String(120)`, and the two drifted: `seed_showcase.py` tagged its products
`"electronics"`, which is not one of the eight canonical slugs.

The visible effect was that the categories page links to
`/search?category=electronics-tech`, and that filter returned **zero reviews**
while four of the six public showcase reviews - the MacBook Air, the Akko
keyboard, the Anker power bank, the Jisulife fan - sat under `"electronics"`,
unreachable through category navigation. Every page still returned HTTP 200.
Nothing failed; the content was just quietly absent.

This rewrites the affected rows onto the canonical slug. It is a pure
relabelling: no row changes category in meaning, only in spelling, and the
mapping is the explicit ALIASES table in `app/core/categories.py` rather than a
fuzzy match. Products with `category IS NULL` are left alone - uncategorised is
a legitimate state that over half of production is in, and inventing a category
for a real product would be guessing.

Safe in either deploy order: relabelling rows cannot break code that reads
them, and `normalize_category()` accepts both spellings.

Downgrade is a deliberate no-op. Reversing would have to rewrite every
`electronics-tech` row back to `electronics`, including the one row that was
always canonical, which would corrupt data this migration never touched. There
is nothing to restore: the canonical spelling is the correct one.

Revision ID: 0027_normalize_product_categories
Revises: 0026_data_integrity_checks
"""
from __future__ import annotations

import re

from alembic import op
from app.core.categories import ALIASES

revision = "0027_normalize_product_categories"
down_revision = "0026_data_integrity_checks"
branch_labels = None
depends_on = None


def _slug(value: str) -> str:
    """A category slug, or an exception. Guards the literal SQL below.

    ALIASES and CATEGORIES are module constants of hardcoded slugs, never user
    input, so interpolating them is safe today. This makes that a property the
    code enforces rather than one a future editor has to remember.
    """
    if not re.fullmatch(r"[a-z0-9-]+", value or ""):
        raise ValueError(f"not a category slug: {value!r}")
    return value


def upgrade() -> None:
    from alembic import context

    # `alembic upgrade head --sql` renders SQL without a database. There is
    # nothing to inspect in that mode: `op.execute` returns None, so reading
    # `.rowcount` raises, and the diagnostic SELECT below cannot run at all.
    # Offline rendering is how this migration gets reviewed before it is
    # applied, and how a fresh database is built where no direct connection is
    # available - both of which this previously made impossible.
    if context.is_offline_mode():
        for wrong, right in ALIASES.items():
            op.execute(f"UPDATE products SET category = '{_slug(right)}' "
                       f"WHERE category = '{_slug(wrong)}'")
        return

    from sqlalchemy import text

    conn = op.get_bind()
    for wrong, right in ALIASES.items():
        result = conn.execute(
            text("UPDATE products SET category = :right WHERE category = :wrong"),
            {"right": right, "wrong": wrong})
        if result.rowcount:
            print(f"  category {wrong!r} -> {right!r}: {result.rowcount} product(s)")

    # Anything still outside the vocabulary is a slug nobody predicted. Report
    # it rather than guessing - a wrong category is not better than none.
    from app.core.categories import CATEGORIES
    stray = conn.execute(text(
        "SELECT DISTINCT category FROM products "
        "WHERE category IS NOT NULL AND category <> '' "
        "AND category <> ALL(:known)"), {"known": list(CATEGORIES)}).scalars().all()
    if stray:
        print(f"  WARNING: {len(stray)} category value(s) outside the vocabulary "
              f"and left untouched: {', '.join(map(repr, stray))}")


def downgrade() -> None:
    """Intentionally empty - see the module docstring."""
