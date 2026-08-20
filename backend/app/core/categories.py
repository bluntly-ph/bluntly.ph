"""The product category vocabulary, owned by the backend.

Until now this list existed nowhere in the backend at all: `products.category`
was an unconstrained `String(120)`, and the slugs lived only in the frontend -
in *two* files that had already drifted from each other.

  * `lib/landing-data.ts` (`CATEGORIES`) is what the categories page and the
    search chips render, so it decides what a product can be *browsed* under.
  * `lib/interests.ts` (`INTERESTS`) is what onboarding step 2 offers, and its
    slugs are stored on `users.interests`.

The vocabulary here is the union of the two, minus `trending`, which both
frontend pages filter out explicitly - it is a rail label, not a category any
product is filed under.

What the drift cost: `seed_showcase.py` tagged four products `"electronics"`,
a slug neither frontend list has ever contained. The categories page links to
`/search?category=electronics-tech`, that filter matched nothing, and four of
the six public showcase reviews were unreachable through category navigation
while every page still returned HTTP 200. Nothing failed. The content was just
quietly absent, which is the whole problem with a free-text column standing in
for a shared vocabulary.

`backend/tests/test_categories.py` reads both frontend files off disk and fails
if either drifts from this one. See `docs/CATEGORIES.md`.
"""

from __future__ import annotations

# slug -> label, in the order the categories page presents them.
CATEGORIES: dict[str, str] = {
    "audio": "Audio",
    "automotive": "Automotive",
    "beauty": "Beauty",
    "electronics-tech": "Electronics & Tech",
    "fashion-accessories": "Fashion & Accessories",
    "food": "Food",
    "gaming": "Gaming",
    "health-fitness": "Health & Fitness",
    "home-appliances": "Home Appliances",
    "home-living": "Home & Living",
    "kids-toys": "Kids & Toys",
    "office-productivity": "Office & Productivity",
    "sports-outdoors": "Sports & Outdoors",
    "pets": "Pets",
}

# Spellings that actually reached the database before the vocabulary had an
# owner. Deliberately only the observed ones: a guessed alias is a guess about
# what somebody meant, and guessing wrong files a product under the wrong
# category silently - the same failure this module exists to end. `"home"`, for
# one, could reasonably mean either `home-living` or `home-appliances`, so it
# is not here.
ALIASES: dict[str, str] = {
    "electronics": "electronics-tech",
    "tech": "electronics-tech",
}


class UnknownCategory(ValueError):
    """Raised for a slug that is neither canonical nor a known alias."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"unknown category {value!r}. Valid: {', '.join(sorted(CATEGORIES))}")
        self.value = value


def normalize_category(value: str | None) -> str | None:
    """Canonical slug for `value`, or None when there is no category.

    None and blank both mean "not categorised", which is a legitimate state -
    over half of production is in it. Only a non-empty value that resolves to
    nothing is an error, because storing it would repeat the original defect.
    """
    if value is None:
        return None
    slug = value.strip().lower()
    if not slug:
        return None
    if slug in CATEGORIES:
        return slug
    if slug in ALIASES:
        return ALIASES[slug]
    raise UnknownCategory(value)


def spellings_for(value: str) -> list[str]:
    """Every stored spelling that should match a requested category.

    Filtering is deliberately forgiving where writing is strict. A row written
    before the vocabulary had an owner still holds its old spelling, and until
    0027 has been applied everywhere, asking for `electronics-tech` has to find
    the products stored as `electronics` - otherwise the category page is empty
    and the reader has no idea why.

    An unrecognised value returns itself, so an unknown category matches
    nothing instead of raising. A reader typing a bad slug into the URL should
    see no results, not a 500.
    """
    slug = (value or "").strip().lower()
    if not slug:
        return []
    canonical = slug if slug in CATEGORIES else ALIASES.get(slug, slug)
    return sorted({canonical, slug, *(w for w, r in ALIASES.items() if r == canonical)})
