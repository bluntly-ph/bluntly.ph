"""Minimal product routes (M1) — enough to support review submission.

Full manual canonicalization (pending->canonicalized admin queue) is a separate
concern from the original capstone docs; here a created product is immediately
usable so the review flow works end-to-end.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, NotFoundError
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import MemberRole, ProductStatus, VerificationStatus
from app.models.product import Product
from app.models.review import Review
from app.models.user import User
from app.schemas.product import (
    ComparisonEntry,
    ComparisonOut,
    PriceObservationIn,
    PriceObservationOut,
    PricePanelOut,
    ProductCanonicalize,
    ProductCreate,
    ProductOut,
)
from app.services import price_service
from app.services.trust_rating_service import product_low_trust

router = APIRouter(prefix="/products", tags=["products"])

# FR-2 says "side-by-side"; two is the fewest that compares and four is the
# most that stays readable on a phone without becoming a spreadsheet.
COMPARE_MIN = 2
COMPARE_MAX = 4


def _get_product_or_404(db: Session, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.", code="product_not_found")
    return product


def _panel_out(product_id: uuid.UUID, panel) -> PricePanelOut:
    return PricePanelOut(
        product_id=product_id,
        sufficient=panel.sufficient,
        observation_count=panel.observation_count,
        independent_count=panel.independent_count,
        required_independent=price_service.MIN_INDEPENDENT_OBSERVATIONS,
        currency=panel.currency,
        low=panel.low, high=panel.high, median=panel.median,
        latest_observed_at=panel.latest_observed_at,
        platforms=list(panel.platforms),
    )


def _verified_counts(db: Session, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Published, non-removed, verified reviews per product, in one query.

    FR-2 asks comparison to use *verified* review scores, so the count that
    belongs beside the average is the verified one, not the total."""
    if not product_ids:
        return {}
    rows = db.execute(
        select(Review.product_id, func.count(Review.id))
        .where(Review.product_id.in_(product_ids),
               Review.published_at.isnot(None),
               Review.is_removed.is_(False),
               Review.verification_status == VerificationStatus.verified)
        .group_by(Review.product_id)
    ).all()
    return {pid: count for pid, count in rows}


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
    """Submit a product.

    A reviewer submits a *marketplace link* and the row lands `pending`, which
    is what ProductStatus.pending has always documented itself as meaning
    ("submitted via source_url, awaiting canonicalization"). The route used to
    shortcut straight to `canonicalized` with whatever name the reviewer typed
    (BUG-020) — so "Jisulife fan", "jisulife life9" and "JISULIFE Life 9" became
    three products, splitting the reviews that should consolidate under one.

    The name a reviewer types is kept as a provisional label so the product is
    recognisable in the meantime; a moderator replaces it via /canonicalize.
    Moderators still create canonicalized rows directly — they are the ones
    doing the naming, and they may be adding something with no listing at all.

    `source_url` is deliberately *not* enforced here even though the write-review
    form always sends one. Requiring it would be a breaking contract change for
    every existing caller — seeds, scripts, and a dozen test fixtures create
    products by name alone — to re-state a rule the only human-facing path
    already applies. The status is what protects the catalogue: an unnamed
    submission stays `pending` whether or not a link came with it.
    """
    is_moderator = user.role == MemberRole.moderator
    product = Product(
        canonical_name=payload.name, category=payload.category, brand=payload.brand,
        source_url=payload.source_url, submitted_by=user.id,
        status=ProductStatus.canonicalized if is_moderator else ProductStatus.pending,
        product_id=f"prd_{uuid.uuid4().hex[:10]}",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return ProductOut.model_validate(product)


@router.post("/{product_id}/canonicalize", response_model=ProductOut,
             summary="Set a pending product's canonical name (moderator)")
def canonicalize_product(product_id: uuid.UUID, payload: ProductCanonicalize,
                         db: Session = Depends(get_db),
                         mod: User = Depends(require_role("moderator"))) -> ProductOut:
    """Name a submission and admit it to the catalogue (BUG-020)."""
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.", code="product_not_found")
    product.canonical_name = payload.canonical_name()
    product.brand = payload.brand
    if payload.category:
        product.category = payload.category
    product.status = ProductStatus.canonicalized
    db.commit()
    db.refresh(product)
    return _product_out(product)


@router.get("", response_model=list[ProductOut], summary="List products")
def list_products(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=100),
                  q: str | None = Query(None, max_length=200),
                  include_low_trust: bool = False) -> list[ProductOut]:
    stmt = select(Product)
    if q and q.strip():
        stmt = stmt.where(Product.canonical_name.ilike(f"%{q.strip()}%"))
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


@router.get("/compare", response_model=ComparisonOut,
            summary="Side-by-side comparison of 2-4 products (FR-2)")
def compare_products(ids: str, db: Session = Depends(get_db)) -> ComparisonOut:
    """Compare products on verified review signal and community price data.

    Public: FR-2 says browsing does not require an account, and comparison is a
    browsing activity.

    Unknown ids are returned in `not_found` rather than 404ing the whole
    request. A shared comparison link outliving one of its products is normal,
    and losing the other three columns to it would be the wrong trade.

    Seller ratings are deliberately absent even though FR-2 lists them: seller
    reviews were withdrawn from contract on 2026-07-28 (MILESTONES.md). There
    is no truthful value to put in that column, and inventing one on a platform
    about honest reviews is not a defensible shortcut.
    """
    raw = [part.strip() for part in ids.split(",") if part.strip()]
    if not (COMPARE_MIN <= len(raw) <= COMPARE_MAX):
        raise AppError(
            f"Compare between {COMPARE_MIN} and {COMPARE_MAX} products.",
            code="compare_count", status_code=422, title="Invalid comparison")

    wanted: list[uuid.UUID] = []
    missing: list[uuid.UUID] = []
    for part in raw:
        try:
            parsed = uuid.UUID(part)
        except ValueError:
            raise AppError("Product ids must be UUIDs.", code="compare_bad_id",
                           status_code=422, title="Invalid comparison") from None
        if parsed not in wanted:
            wanted.append(parsed)

    found = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(wanted)))}
    panels = price_service.panels_for(db, [pid for pid in wanted if pid in found])
    verified = _verified_counts(db, [pid for pid in wanted if pid in found])

    entries = []
    for pid in wanted:
        product = found.get(pid)
        if product is None:
            missing.append(pid)
            continue
        entries.append(ComparisonEntry(
            product=_product_out(product),
            price=_panel_out(pid, panels.get(pid)),
            review_count=product.review_count or 0,
            avg_rating=product.avg_rating,
            trust_score=product.trust_score,
            verified_review_count=verified.get(pid, 0),
        ))
    return ComparisonOut(entries=entries, not_found=missing)


@router.get("/{product_id}", response_model=ProductOut,
            summary="Get a product (always retrievable; low_trust computed)")
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.", code="product_not_found")
    return _product_out(product)


# --------------------------------------------------------------------------
# FR-2: community price observations, the price panel, and comparison.
#
# `/compare` is declared before `/{product_id}` so the literal path wins the
# match; otherwise "compare" is parsed as a product UUID and 422s.
# --------------------------------------------------------------------------

@router.get("/{product_id}/prices", response_model=PricePanelOut,
            summary="Community price panel for a product (FR-2)")
def get_price_panel(product_id: uuid.UUID,
                    db: Session = Depends(get_db)) -> PricePanelOut:
    """Public. Returns an insufficient-data panel rather than 404 when sparse."""
    _get_product_or_404(db, product_id)
    return _panel_out(product_id, price_service.get_panel(db, product_id))


@router.post("/{product_id}/prices", response_model=PriceObservationOut,
             status_code=201,
             summary="Submit a community price observation (FR-2)")
def submit_price(product_id: uuid.UUID, payload: PriceObservationIn,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> PriceObservationOut:
    """Authenticated: an observation is attributable or it is not independent.

    The threshold counts distinct submitters, so an anonymous observation could
    never be counted anyway - and an unattributable price on a platform built
    around accountable contributions is worse than no price.
    """
    _get_product_or_404(db, product_id)
    row = price_service.submit_observation(
        db, product_id, user.id, payload.platform, payload.price,
        payload.observed_at, payload.variant)
    return PriceObservationOut.model_validate(row)
