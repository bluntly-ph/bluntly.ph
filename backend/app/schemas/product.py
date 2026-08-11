"""Minimal product schemas (M1 — enough to support review submission)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProductStatus


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = None
    brand: str | None = None
    # Required in practice for reviewer submissions (BUG-020) — the route
    # enforces it by role, because a moderator adding a product directly has no
    # marketplace listing to point at.
    source_url: str | None = Field(default=None, max_length=2048)


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
    category: str | None = None

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
