"""The product category vocabulary, owned by the backend.

Until now this list existed only in the frontend (`lib/interests.ts`), while
`products.category` was an unconstrained `String(120)`. Two halves of one
vocabulary, with nothing keeping them in step - and they drifted:
`seed_showcase.py` tagged four products `"electronics"`, a slug the frontend
has never had. The categories page links to `/search?category=electronics-tech`,
so those four reviews - two thirds of the public showcase - were unreachable
through category navigation while every page still returned HTTP 200.

Nothing could have caught that. A free-text column accepts any spelling, and
the failure is silent: no error, no empty result anywhere a test was looking,
just a category page quietly missing its contents.

So the slugs live here, the API refuses one it does not know, and
`docs/CATEGORIES.md` records that the two lists must change together.

The slugs are the frontend's, verbatim - they are already stored in
`users.interests` from onboarding, so this list is the one that had to move.
"""

from __future__ import annotations

# slug -> human label. Order matches lib/interests.ts, which is the order the
# onboarding wizard and the categories page present.
CATEGORIES: dict[str, str] = {
    "electronics-tech": "Electronics & Tech",
    "office-productivity": "Office & Productivity",
    "audio": "Audio",
    "home-living": "Home & Living",
    "beauty": "Beauty",
    "fashion-accessories": "Fashion & Accessories",
    "automotive": "Automotive",
    "health-fitness": "Health & Fitness",
}

# Spellings that were written before the vocabulary had an owner. Kept as a
# deliberate, visible mapping rather than a silent fuzzy match: each entry is a
# mistake that actually reached the database, and 0027 normalises the rows.
ALIASES: dict[str, str] = {
    "electronics": "electronics-tech",
    "tech": "electronics-tech",
    "fashion": "fashion-accessories",
    "home": "home-living",
    "health": "health-fitness",
    "office": "office-productivity",
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
    over half of production carries it. Only a non-empty value that resolves to
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
