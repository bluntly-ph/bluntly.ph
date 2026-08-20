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


class TestReadIsForgivingWhereWriteIsStrict:
    """Filtering must find rows written before the vocabulary had an owner.

    Until 0027 is applied everywhere, `?category=electronics-tech` has to match
    products still stored as `electronics` - otherwise the category page is
    empty and the reader is given no reason why.
    """

    def test_the_canonical_slug_finds_the_old_spelling(self):
        from app.core.categories import spellings_for
        assert "electronics" in spellings_for("electronics-tech")

    def test_the_old_spelling_finds_the_canonical_rows(self):
        from app.core.categories import spellings_for
        assert "electronics-tech" in spellings_for("electronics")

    def test_a_category_with_no_aliases_matches_only_itself(self):
        from app.core.categories import spellings_for
        assert spellings_for("beauty") == ["beauty"]

    def test_an_unknown_slug_matches_nothing_rather_than_raising(self):
        """A bad slug in the URL is a reader's typo, not a server error."""
        from app.core.categories import spellings_for
        assert spellings_for("sporting-goods") == ["sporting-goods"]

    def test_no_category_means_no_filter(self):
        from app.core.categories import spellings_for
        assert spellings_for("") == [] and spellings_for("   ") == []

    def test_the_feed_query_uses_the_alias_set(self):
        """Pins the wiring, not just the helper - the bug was in the wiring."""
        import inspect

        from app.services import review_service
        src = inspect.getsource(review_service)
        assert "spellings_for(category)" in src, (
            "the feed no longer filters through the alias set; a product stored "
            "under a legacy spelling will vanish from its category page")
