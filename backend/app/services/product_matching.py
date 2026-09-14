"""Duplicate product detection at submission (FR-2 2.8).

BUG-020 found "Jisulife fan", "jisulife life9" and "JISULIFE Life 9" as three
products, splitting reviews that should consolidate under one. Moderator
canonicalisation fixes a name after the fact; this module stops the most
mechanical duplicates at the moment of submission:

* **the same listing** — a marketplace link pasted again with different
  tracking parameters, fragment, `www.` or trailing slash;
* **the same name** — identical once case, spacing and punctuation are set
  aside.

Only an exact match on those keys counts. "Jisulife Life 9" and "Jisulife Life 9
Pro" stay two products: a near-match is a moderator's judgement, and an
automatic merge that is wrong puts one product's reviews on another.

Both keys are computed in Python for the request and in SQL for the stored
rows, with the same rules (lowercase, `[^a-z0-9]+` → space), so the two sides
cannot disagree. Rejected submissions never match.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ProductStatus
from app.models.product import Product

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WWW = re.compile(r"^(https?://)www\.")

#: A rejected submission is not a product anyone should be folded into.
_MATCHABLE = (ProductStatus.pending, ProductStatus.canonicalized)


def name_key(name: str | None) -> str | None:
    """Lowercased, with every run of non-[a-z0-9] collapsed to one space.

    `lower()` rather than `casefold()`, because the SQL side is `lower()`: the
    two must produce the same key for the same text.
    """
    if not name:
        return None
    key = _NON_ALNUM.sub(" ", name.lower()).strip()
    return key or None


def listing_key(url: str | None) -> str | None:
    """A listing URL without query, fragment, `www.` or trailing slash, lowercased."""
    if not url or not url.strip():
        return None
    base = url.strip().split("#", 1)[0].split("?", 1)[0].lower()
    base = _WWW.sub(r"\1", base).rstrip("/")
    return base or None


def _sql_name_key():
    return func.trim(func.regexp_replace(func.lower(Product.canonical_name),
                                         "[^a-z0-9]+", " ", "g"))


def _sql_listing_key():
    without_query = func.split_part(func.split_part(Product.source_url, "#", 1), "?", 1)
    return func.rtrim(
        func.regexp_replace(func.lower(without_query), r"^(https?://)www\.", r"\1"), "/")


def find_existing_product(db: Session, *, name: str | None,
                          source_url: str | None) -> Product | None:
    """The existing product this submission duplicates, or None.

    The listing is checked first: a pasted marketplace link is stronger
    evidence of "the same product" than a typed name. The oldest match wins,
    so repeated duplicates all fold into the original rather than into each
    other.
    """
    base = (select(Product)
            .where(Product.status.in_(_MATCHABLE))
            .order_by(Product.created_at)
            .limit(1))

    by_listing = listing_key(source_url)
    if by_listing is not None:
        found = db.scalar(base.where(Product.source_url.isnot(None),
                                     _sql_listing_key() == by_listing))
        if found is not None:
            return found

    by_name = name_key(name)
    if by_name is not None:
        return db.scalar(base.where(Product.canonical_name.isnot(None),
                                    _sql_name_key() == by_name))
    return None
