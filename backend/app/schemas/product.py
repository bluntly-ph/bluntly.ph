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
    source_url: str | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: str | None = None
    canonical_name: str | None = None
    category: str | None = None
    status: ProductStatus
    avg_rating: Decimal
    review_count: int
    # Trust rating + computed visibility flag (M2 slice 4).
    trust_score: Decimal = Decimal("0")
    low_trust: bool = False
    created_at: datetime
