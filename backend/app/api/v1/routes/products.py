"""Minimal product routes (M1) — enough to support review submission.

Full manual canonicalization (pending->canonicalized admin queue) is a separate
concern from the original capstone docs; here a created product is immediately
usable so the review flow works end-to-end.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.enums import ProductStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductOut
from app.services.trust_rating_service import product_low_trust

router = APIRouter(prefix="/products", tags=["products"])


def _product_out(product: Product) -> ProductOut:
    out = ProductOut.model_validate(product)
    out.low_trust = product_low_trust(
        product,
        threshold=settings.product_trust_visibility_threshold,
        min_reviews=settings.product_trust_min_reviews,
    )
    return out


@router.post("", response_model=ProductOut, status_code=201, summary="Create a product")
def create_product(payload: ProductCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> ProductOut:
    product = Product(
        canonical_name=payload.name, category=payload.category, brand=payload.brand,
        source_url=payload.source_url, submitted_by=user.id,
        status=ProductStatus.canonicalized, product_id=f"prd_{uuid.uuid4().hex[:10]}",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return ProductOut.model_validate(product)


@router.get("", response_model=list[ProductOut], summary="List products")
def list_products(db: Session = Depends(get_db), limit: int = 50,
                  include_low_trust: bool = False) -> list[ProductOut]:
    stmt = select(Product)
    # Visibility threshold (M2 slice 4): with enough reviews and a trust score
    # below the configured floor, a product drops out of the default listing.
    # Threshold 0.0 (default) disables the filter entirely.
    if not include_low_trust and settings.product_trust_visibility_threshold > 0:
        stmt = stmt.where(or_(
            Product.review_count < settings.product_trust_min_reviews,
            Product.trust_score >= settings.product_trust_visibility_threshold,
        ))
    rows = db.scalars(stmt.order_by(Product.created_at.desc()).limit(limit))
    return [_product_out(p) for p in rows]


@router.get("/{product_id}", response_model=ProductOut,
            summary="Get a product (always retrievable; low_trust computed)")
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.", code="product_not_found")
    return _product_out(product)
