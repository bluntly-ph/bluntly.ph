"""Minimal product schemas (M1 — enough to support review submission)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.categories import CATEGORIES, normalize_category
from app.models.enums import Platform, ProductStatus
from app.schemas.urls import web_url_or_none

# Published in the OpenAPI schema so the contract states what a category may
# be. The server also accepts the legacy spellings in `ALIASES` and normalises
# them, which is deliberately more lenient than what is documented here.
CATEGORY_FIELD = Field(
    default=None,
    description=("Product category. One of the slugs in "
                 "`backend/app/core/categories.py`, which the frontend renders "
                 "as chips on /categories. Null means uncategorised."),
    json_schema_extra={"enum": [*CATEGORIES, None]},
)


# The Philippines is UTC+8 all year - no daylight saving - so a fixed offset is
# exact here and avoids depending on a tz database being present on the host.
PH_TIMEZONE = timezone(timedelta(hours=8))


def _ph_today() -> date:
    """Today, as the reader experiences it.

    The platform is Philippines-specific by design (PRD S1), so "today" means
    today in Manila. Server-local `date.today()` is UTC in production and is a
    different day for a third of every one.
    """
    return datetime.now(PH_TIMEZONE).date()


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = CATEGORY_FIELD
    brand: str | None = None
    # Required in practice for reviewer submissions (BUG-020) — the route
    # enforces it by role, because a moderator adding a product directly has no
    # marketplace listing to point at.
    source_url: str | None = Field(default=None, max_length=2048)

    # The moderator queue renders this as a clickable link (ModerationQueue.tsx),
    # so it is a submitter-chosen string that a moderator activates.
    @field_validator("source_url")
    @classmethod
    def _only_web_source(cls, value: str | None) -> str | None:
        return web_url_or_none(value, field="Listing links")

    # A category the frontend cannot render is worse than none: the product
    # simply vanishes from category navigation, silently. See app/core/categories.py.
    @field_validator("category")
    @classmethod
    def _canonical_category(cls, v: str | None) -> str | None:
        return normalize_category(v)


class ProductCanonicalize(BaseModel):
    """A moderator's canonical naming of a pending submission (BUG-020).

    The four parts the naming convention asks for are separate fields rather
    than one free-text box, because that is what keeps two people naming the
    same product the same way — which is the entire point of consolidating
    reviews under one entry.
    """

    brand: str = Field(min_length=1, max_length=120)
    product_line: str = Field(min_length=1, max_length=160)
    key_spec: str | None = Field(default=None, max_length=120)
    descriptor: str | None = Field(default=None, max_length=120)
    category: str | None = CATEGORY_FIELD


    # A category the frontend cannot render is worse than none: the product
    # simply vanishes from category navigation, silently. See app/core/categories.py.
    @field_validator("category")
    @classmethod
    def _canonical_category(cls, v: str | None) -> str | None:
        return normalize_category(v)

    def canonical_name(self) -> str:
        parts = [self.brand, self.product_line, self.key_spec, self.descriptor]
        return " ".join(p.strip() for p in parts if p and p.strip())


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: str | None = None
    canonical_name: str | None = None
    category: str | None = None
    status: ProductStatus
    avg_rating: Decimal
    review_count: int
    # See FeedProduct.image_url (BUG-009).
    image_url: str | None = None
    # Trust rating + computed visibility flag (M2 slice 4).
    trust_score: Decimal = Decimal("0")
    low_trust: bool = False
    created_at: datetime


class PriceObservationIn(BaseModel):
    """One community-submitted purchase price (FR-2)."""

    platform: Platform
    price: Decimal = Field(gt=0, le=Decimal("10000000"),
                           description="Price actually paid, in PHP.")
    observed_at: date = Field(description="The date this price was seen or paid.")
    variant: str | None = Field(default=None, max_length=120)

    @field_validator("observed_at")
    @classmethod
    def _not_in_the_future(cls, value: date) -> date:
        # A price cannot have been paid tomorrow. Cheap to check here, and it
        # keeps `latest_observed_at` on the panel honest.
        #
        # Against the *Philippine* date, not the server's. `date.today()` is
        # UTC on Vercel, and Manila is UTC+8 - so for eight hours of every day
        # (UTC 16:00-23:59, i.e. midnight to 08:00 in Manila) a reader entering
        # the price they paid today was told it was in the future. A third of
        # each day, for the only audience this platform has.
        if value > _ph_today():
            raise ValueError("observed_at cannot be in the future.")
        return value


class PriceObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    platform: Platform
    price: Decimal
    observed_at: date
    variant: str | None = None
    created_at: datetime


class PricePanelOut(BaseModel):
    """The panel, or the reason it is not shown yet.

    `sufficient` is false until at least 3 INDEPENDENT observations exist
    (FR-2), and the price fields are null in that state - the UI is given the
    counts so it can say how many more are needed, not prices to hide.
    """

    product_id: uuid.UUID
    sufficient: bool
    observation_count: int
    independent_count: int
    required_independent: int
    currency: str = "PHP"
    low: Decimal | None = None
    high: Decimal | None = None
    median: Decimal | None = None
    latest_observed_at: date | None = None
    platforms: list[str] = Field(default_factory=list)


class ComparisonEntry(BaseModel):
    """One column of the side-by-side comparison (FR-2)."""

    product: ProductOut
    price: PricePanelOut
    # Verified review signal. Seller ratings are deliberately absent: FR-2 named
    # them, but seller reviews were withdrawn from contract on 2026-07-28
    # (MILESTONES.md), so there is nothing truthful to put here.
    review_count: int
    avg_rating: Decimal | None = None
    trust_score: Decimal | None = None
    verified_review_count: int = 0


class ComparisonOut(BaseModel):
    entries: list[ComparisonEntry]
    not_found: list[uuid.UUID] = Field(default_factory=list)
