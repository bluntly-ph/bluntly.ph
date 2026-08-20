"""The category vocabulary is shared across three files, so it gets a test.

The defect this exists to prevent was silent. `products.category` was free
text, the slugs lived only in the frontend, and `seed_showcase.py` wrote
`"electronics"` where every frontend list said `"electronics-tech"`. Result:
`/search?category=electronics-tech` returned nothing while four of the six
public showcase reviews sat one spelling away, and every page still answered
HTTP 200.

The frontend keeps the vocabulary in two files, for two different jobs, and
they had already drifted from each other before the backend had any opinion:

  * `lib/landing-data.ts` decides what a product can be *browsed* under.
  * `lib/interests.ts` decides what a user can express an *interest* in.

So this reads both off disk. Checking only one is exactly how six categories
the site advertises - food, gaming, pets, and the rest - came within a commit
of being rejected by the very validation meant to protect them.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from app.core.categories import ALIASES, CATEGORIES, UnknownCategory, normalize_category

ROOT = pathlib.Path(__file__).resolve().parents[2]
LANDING_TS = ROOT / "lib" / "landing-data.ts"
INTERESTS_TS = ROOT / "lib" / "interests.ts"

# Not a product category: both the categories page and the search chips filter
# it out explicitly. It labels a rail.
NOT_A_CATEGORY = {"trending"}


def landing_slugs() -> set[str]:
    src = LANDING_TS.read_text(encoding="utf-8")
    block = src.split("export const CATEGORIES")[1].split("];")[0]
    return set(re.findall(r'slug: "([a-z0-9-]+)"', block)) - NOT_A_CATEGORY


def interest_slugs() -> set[str]:
    src = INTERESTS_TS.read_text(encoding="utf-8")
    return set(re.findall(r'slug:\s*"([a-z0-9-]+)"', src))


frontend = pytest.mark.skipif(
    not (LANDING_TS.exists() and INTERESTS_TS.exists()),
    reason="frontend not checked out")


@frontend
def test_every_browsable_category_is_in_the_vocabulary():
    """A category with a chip the API refuses is a category nobody can file under."""
    missing = landing_slugs() - set(CATEGORIES)
    assert not missing, (
        f"lib/landing-data.ts offers {sorted(missing)}, which the API would "
        "reject. The site advertises a category no product can be filed under.")


@frontend
def test_every_onboarding_interest_is_in_the_vocabulary():
    """An interest with no matching category matches no products, forever."""
    missing = interest_slugs() - set(CATEGORIES)
    assert not missing, f"lib/interests.ts offers {sorted(missing)}, unknown to the API"


@frontend
def test_the_vocabulary_has_nothing_the_frontend_cannot_show():
    """The reverse drift: a slug the API accepts but nothing renders."""
    orphans = set(CATEGORIES) - landing_slugs() - interest_slugs()
    assert not orphans, (
        f"the API accepts {sorted(orphans)} but no frontend list shows them - "
        "products filed there would be invisible")


@frontend
def test_an_interest_can_actually_be_browsed():
    """Picking an interest in onboarding should lead somewhere.

    `audio` was offered in onboarding while the categories page had no Audio
    chip, so the one interest could never be browsed.
    """
    unbrowsable = interest_slugs() - landing_slugs()
    assert not unbrowsable, (
        f"{sorted(unbrowsable)} can be chosen in onboarding but has no category "
        "chip, so a user who picks it can never browse it")


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
                               category="tech").category == "electronics-tech"
    # A category the site advertises must survive the round trip untouched.
    assert ProductCreate(name="x", category="gaming").category == "gaming"
    assert ProductCreate(name="x", category="pets").category == "pets"


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
