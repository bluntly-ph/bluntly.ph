"""Review submission, editing (with version history), and product aggregates (M1)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.categories import spellings_for
from app.core.config import settings
from app.core.errors import NotFoundError
from app.models.enums import EarnEligibleStatus, VerificationStatus
from app.models.product import Product
from app.models.review import Review, ReviewVersion
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewUpdate
from app.services.storage import review_photo_belongs_to

# Fields captured in each version snapshot.
#
# receipt_key is deliberately absent. Snapshots are served by
# GET /reviews/{id}/versions[/{n}], which accept anonymous callers for any
# published review - so anything in here is public. The edit history records
# `receipt_present` instead, which preserves the audit fact (evidence was
# attached, or removed) without publishing where the object lives.
VERSIONED_FIELDS = (
    "title", "discussion", "verdict", "verdict_explanation", "target_audience",
    "anti_target_audience", "star_rating", "pros", "cons", "photo_url",
    "price_paid",
)


def _verification_for(photo_url: str | None,
                      author_id: uuid.UUID) -> VerificationStatus:
    """Verified only when the proof photo is an object this author uploaded.

    FR-3 makes a proof photo the thing that verifies a review, so "is this
    field non-empty" was never the real question - "did this author upload
    this object" is. Before, any string in `photo_url` earned the badge, so a
    reviewer could paste someone else's photo, or a URL to nothing at all, and
    be verified for it.

    The route checks ownership too and returns 403, which is the better answer
    for a caller who got it wrong. This exists because the decision belongs
    next to its precondition: a seed script, an admin path or a new endpoint
    that reaches the service directly must not be able to mint a verified
    review, and one day one of them will.

    Unverified rather than an exception: the service's job is to say what it
    can vouch for. Refusing to vouch is a complete answer, and it cannot be
    turned into an exploit by a caller that ignores it.
    """
    if photo_url and review_photo_belongs_to(photo_url, author_id):
        return VerificationStatus.verified
    return VerificationStatus.unverified


def _snapshot(review: Review) -> dict:
    snap: dict = {}
    for field in VERSIONED_FIELDS:
        value = getattr(review, field)
        if field == "verdict" and value is not None:
            value = value.value
        elif field == "price_paid" and value is not None:
            value = str(value)
        snap[field] = value
    snap["receipt_present"] = bool(review.receipt_key)
    return snap


def recompute_product_aggregates(db: Session, product_id: uuid.UUID) -> None:
    """Service-layer aggregate update (ADR: no DB triggers).

    Counts only **published**, non-removed reviews (publication gate, M2 slice 1).
    Also refreshes the product's Wilson trust rating (M2 slice 4) since both move
    on the same events: publish / unpublish / star edit.

    Sessions run with autoflush=False, so flush first — callers invoke this right
    after mutating review state in-memory, and the aggregate SELECTs below must
    see those pending writes.
    """
    db.flush()
    stats = db.execute(
        select(func.count(Review.id), func.coalesce(func.avg(Review.star_rating), 0))
        .where(Review.product_id == product_id, Review.is_removed.is_(False),
               Review.published_at.isnot(None))
    ).one()
    product = db.get(Product, product_id)
    if product is not None:
        product.review_count = int(stats[0])
        product.avg_rating = round(float(stats[1]), 2)
    from app.services.trust_rating_service import recompute_product_trust
    recompute_product_trust(db, product_id)


def create_review(db: Session, author_id: uuid.UUID, payload: ReviewCreate) -> Review:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise NotFoundError("Product not found.", code="product_not_found")

    review = Review(
        product_id=payload.product_id,
        author_id=author_id,
        title=payload.title,
        discussion=payload.discussion,
        verdict=payload.verdict,
        verdict_explanation=payload.verdict_explanation,
        target_audience=payload.target_audience,
        anti_target_audience=payload.anti_target_audience,
        star_rating=payload.star_rating,
        pros=payload.pros,
        cons=payload.cons,
        photo_url=payload.photo_url,
        receipt_key=payload.receipt_key,
        price_paid=payload.price_paid,
        # Proof photo at submission => verified (FR-3), but only if the
        # photo is genuinely this author's upload. See _verification_for.
        verification_status=_verification_for(payload.photo_url, author_id),
        review_id=f"rev_{uuid.uuid4().hex[:10]}",
        current_version=1,
        # Publication gate (M2 slice 1): hidden + auto-queued for the moderator.
        published_at=None,
        earn_eligible_status=(EarnEligibleStatus.pending if settings.earn_eligible_auto_queue
                              else EarnEligibleStatus.none),
    )
    db.add(review)
    db.flush()
    db.add(ReviewVersion(review_id=review.id, version_number=1,
                         snapshot=_snapshot(review), edited_by=author_id,
                         change_note="initial submission"))
    # New review is unpublished, so aggregates are unchanged; recompute is a no-op
    # here but harmless and keeps the invariant obvious.
    recompute_product_aggregates(db, review.product_id)
    db.commit()
    db.refresh(review)
    return review


def update_review(db: Session, review: Review, editor_id: uuid.UUID,
                  payload: ReviewUpdate) -> Review:
    data = payload.model_dump(exclude_unset=True)
    change_note = data.pop("change_note", None)

    changed = False
    for field, value in data.items():
        if getattr(review, field) != value:
            setattr(review, field, value)
            changed = True

    if not changed:
        return review  # no-op edit: don't create an empty version

    # Re-derive verification from the (possibly changed) photo, ownership
    # included - an edit must not be a way in either.
    review.verification_status = _verification_for(review.photo_url, review.author_id)
    # A rejected review that gets edited is re-queued for moderation (still hidden).
    if review.earn_eligible_status == EarnEligibleStatus.rejected:
        review.earn_eligible_status = EarnEligibleStatus.pending
    review.current_version += 1
    db.add(ReviewVersion(review_id=review.id, version_number=review.current_version,
                         snapshot=_snapshot(review), edited_by=editor_id,
                         change_note=change_note))
    recompute_product_aggregates(db, review.product_id)
    db.commit()
    db.refresh(review)
    return review


def get_review_or_404(db: Session, review_id: uuid.UUID) -> Review:
    review = db.get(Review, review_id)
    if review is None or review.is_removed:
        raise NotFoundError("Review not found.", code="review_not_found")
    return review


def list_versions(db: Session, review_id: uuid.UUID) -> list[ReviewVersion]:
    return list(db.scalars(
        select(ReviewVersion).where(ReviewVersion.review_id == review_id)
        .order_by(ReviewVersion.version_number)
    ))


def list_feed(
    db: Session, *, limit: int = 8, product_id: uuid.UUID | None = None,
    author_id: uuid.UUID | None = None, category: str | None = None,
    q: str | None = None, sort: str = "wilson",
) -> list[tuple[Review, User | None, Product | None]]:
    """Published reviews with their author + product, for public card surfaces.

    Batch-loads authors and products by id (two extra queries total) rather than
    an ORM join, so the shape stays trivial and the N+1 is avoided.
    """
    stmt = select(Review).where(
        Review.is_removed.is_(False), Review.published_at.isnot(None)
    )
    if product_id is not None:
        stmt = stmt.where(Review.product_id == product_id)
    if author_id is not None:
        stmt = stmt.where(Review.author_id == author_id)
    if category or q:
        stmt = stmt.join(Product, Review.product_id == Product.id)
        if category:
            # Alias-tolerant: rows written before the vocabulary had an owner
            # still hold the old spelling. See app/core/categories.py.
            stmt = stmt.where(Product.category.in_(spellings_for(category)))
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(Review.title.ilike(like), Product.canonical_name.ilike(like))
            )
    if sort == "wilson":
        stmt = stmt.order_by(Review.wilson_score.desc(), Review.created_at.desc())
    else:
        stmt = stmt.order_by(Review.created_at.desc())

    reviews = list(db.scalars(stmt.limit(limit)))
    author_ids = {r.author_id for r in reviews if r.author_id is not None}
    product_ids = {r.product_id for r in reviews}
    authors = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(author_ids)))}
        if author_ids else {}
    )
    products = (
        {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids)))}
        if product_ids else {}
    )
    return [(r, authors.get(r.author_id), products.get(r.product_id)) for r in reviews]
