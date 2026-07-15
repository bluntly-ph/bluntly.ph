"""Seller review schemas (M2 slice 4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SellerReviewCreate(BaseModel):
    accuracy: bool
    order_completeness: bool
    customer_service: int = Field(ge=1, le=5)
    packaging_quality: int = Field(ge=1, le=5)
    overall_rating: int = Field(ge=1, le=5)
    would_recommend: bool
    product_id: uuid.UUID | None = None
    proof_url: str | None = None


class SellerReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seller_review_id: str | None = None
    seller_id: uuid.UUID
    reviewer_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    accuracy: bool
    order_completeness: bool
    customer_service: int
    packaging_quality: int
    overall_rating: int
    would_recommend: bool
    proof_url: str | None = None
    created_at: datetime
