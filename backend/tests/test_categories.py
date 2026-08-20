"""The category vocabulary is shared between two codebases, so it gets a test.

The defect this exists to prevent was silent. `products.category` was free
text, the canonical slugs lived only in the frontend, and `seed_showcase.py`
wrote `"electronics"` where the frontend had always said `"electronics-tech"`.
Result: `/search?category=electronics-tech` returned nothing while four of the
six public showcase reviews sat one spelling away, and every page still
answered HTTP 200.

No backend test could have caught it, because the backend had no opinion about
what a category was. Now it does - and this reads the frontend's list off disk
to prove the two still agree.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from app.core.categories import ALIASES, CATEGORIES, UnknownCategory, normalize_category

INTERESTS_TS = pathlib.Path(__file__).resolve().parents[2] / "lib" / "interests.ts"


def frontend_slugs() -> list[str]:
    src = INTERESTS_TS.read_text(encoding="utf-8")
    return re.findall(r'slug:\s*"([a-z0-9-]+)"', src)


@pytest.mark.skipif(not INTERESTS_TS.exists(), reason="frontend not checked out")
def test_the_two_category_lists_are_identical():
    """The whole point. If these drift, category navigation silently empties."""
    frontend = frontend_slugs()
    assert frontend, f"no slugs parsed from {INTERESTS_TS} - the shape changed"
    assert frontend == list(CATEGORIES), (
        "lib/interests.ts and app/core/categories.py disagree.\n"
        f"  frontend: {frontend}\n  backend : {list(CATEGORIES)}\n"
        "Both must change together - see docs/CATEGORIES.md.")


def test_the_alias_that_caused_the_incident():
    assert normalize_category("electronics") == "electronics-tech"


@pytest.mark.parametrize("value", list(CATEGORIES))
def test_every_canonical_slug_survives_normalisation(value):
    assert normalize_category(value) == value


@pytest.mark.parametrize("wrong,right", sorted(ALIASES.items()))
def test_every_alias_resolves_to_a_canonical_slug(wrong, right):
    assert right in CATEGORIES, f"alias {wrong!r} points at {right!r}, which is not canonical"
    assert normalize_category(wrong) == right


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_uncategorised_stays_uncategorised(blank):
    """Over half of production has no category. That is legitimate, not an error."""
    assert normalize_category(blank) is None


def test_an_unknown_slug_is_refused_rather_than_stored():
    with pytest.raises(UnknownCategory):
        normalize_category("sporting-goods")


def test_case_and_padding_do_not_create_a_second_spelling():
    assert normalize_category("  Electronics-Tech  ") == "electronics-tech"


def test_the_api_normalises_on_the_way_in():
    from app.schemas.product import ProductCanonicalize, ProductCreate
    assert ProductCreate(name="x", category="electronics").category == "electronics-tech"
    assert ProductCanonicalize(brand="B", product_line="L",
                               category="fashion").category == "fashion-accessories"


def test_the_api_refuses_a_category_the_frontend_cannot_render():
    from pydantic import ValidationError

    from app.schemas.product import ProductCreate
    with pytest.raises(ValidationError):
        ProductCreate(name="x", category="widgets")
