"""Seller service (FR-4).

The rules that decide whether a seller is a duplicate, and what a store's
public numbers say, are plain functions so they are tested on every machine
(`tests/test_seller_rules.py`). The database-backed flow below is tested in
`tests/test_sellers_api.py`.

Two integrity rules carry the weight here, both refusals of self-dealing in the
same shape as `self_report` and Q&A's `cannot_pick_own_answer`:

* a store's claimed owner cannot rate their own store;
* a moderator cannot decide a claim they submitted themselves.

Claiming never grants ownership by itself. FR-4 limits seller verification to a
moderator cross-checking the store name against the public listing, so a claim
stays `pending` until a moderator decides it.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.models.enums import Platform, SellerClaimStatus
from app.models.product import Product
from app.models.seller import Seller, SellerClaim, SellerReview
from app.models.user import User
from app.schemas.seller import (
    ClaimDecision,
    SellerClaimCreate,
    SellerClaimOut,
    SellerCreate,
    SellerDetailOut,
    SellerOut,
    SellerReviewCreate,
    SellerReviewOut,
    SellerSummary,
)

_WHITESPACE = re.compile(r"\s+")


def normalize_seller_name(name: str) -> str:
    """The key the `(platform, normalized_name)` uniqueness constraint sees.

    Casefolded with every run of whitespace collapsed to one space, so a
    reviewer typing "Anker  Official Store " finds the existing store instead
    of creating a second one and splitting its rating in half.
    """
    collapsed = _WHITESPACE.sub(" ", name).strip().casefold()
    if not collapsed:
        raise ValueError("A seller needs a name.")
    return collapsed


def summarize_reviews(reviews: Iterable[Any]) -> SellerSummary:
    """Aggregate seller reviews into the public summary.

    Rates are the share of positive answers; averages are the mean of the
    graded dimensions, rounded for display. With no reviews every figure is
    None rather than zero — see SellerSummary.
    """
    rows = list(reviews)
    count = len(rows)
    if count == 0:
        return SellerSummary(review_count=0)

    def rate(attribute: str) -> float:
        return round(sum(1 for row in rows if getattr(row, attribute)) / count, 4)

    def mean(attribute: str) -> float:
        return round(sum(getattr(row, attribute) for row in rows) / count, 2)

    return SellerSummary(
        review_count=count,
        accuracy_rate=rate("accuracy"),
        order_completeness_rate=rate("order_completeness"),
        recommend_rate=rate("would_recommend"),
        customer_service_average=mean("customer_service"),
        packaging_quality_average=mean("packaging_quality"),
        overall_average=mean("overall_rating"),
    )


# ---------------------------------------------------------------- sellers

def _by_key(db: Session, platform: Platform, key: str) -> Seller | None:
    return db.scalar(
        select(Seller).where(Seller.platform == platform, Seller.normalized_name == key)
    )


def find_or_create_seller(db: Session, payload: SellerCreate) -> tuple[Seller, bool]:
    """Return the store, creating it only if no matching one exists.

    The second element says whether a row was created. Two reviewers adding
    the same store at the same moment both reach the INSERT; the unique
    constraint refuses the second, and that caller is handed the first's row
    rather than an error.
    """
    try:
        key = normalize_seller_name(payload.display_name)
    except ValueError as exc:
        raise AppError(str(exc), code="seller_name_blank", status_code=422,
                       title="Invalid seller") from exc

    existing = _by_key(db, payload.platform, key)
    if existing is not None:
        return existing, False

    seller = Seller(
        display_name=_WHITESPACE.sub(" ", payload.display_name).strip(),
        normalized_name=key,
        platform=payload.platform,
        store_url=payload.store_url,
    )
    db.add(seller)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _by_key(db, payload.platform, key)
        if existing is None:
            raise
        return existing, False
    db.refresh(seller)
    return seller, True


def get_seller_or_404(db: Session, seller_id: uuid.UUID) -> Seller:
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise NotFoundError("Seller not found.")
    return seller


def list_sellers(db: Session, *, q: str | None, platform: Platform | None,
                 limit: int) -> list[SellerOut]:
    stmt = select(Seller)
    if platform is not None:
        stmt = stmt.where(Seller.platform == platform)
    if q:
        needle = _WHITESPACE.sub(" ", q).strip().casefold()
        if needle:
            stmt = stmt.where(Seller.normalized_name.contains(needle, autoescape=True))
    stmt = stmt.order_by(Seller.display_name).limit(limit)
    return [SellerOut.model_validate(s) for s in db.scalars(stmt).all()]


def get_seller_detail(db: Session, seller_id: uuid.UUID) -> SellerDetailOut:
    seller = get_seller_or_404(db, seller_id)
    reviews = db.scalars(
        select(SellerReview).where(SellerReview.seller_id == seller.id)
    ).all()
    return SellerDetailOut(
        **SellerOut.model_validate(seller).model_dump(),
        summary=summarize_reviews(reviews),
    )


# ---------------------------------------------------------------- reviews

def create_seller_review(db: Session, seller: Seller, reviewer: User,
                         payload: SellerReviewCreate) -> SellerReviewOut:
    if seller.claimed_by_id is not None and seller.claimed_by_id == reviewer.id:
        raise AppError("You cannot rate a store you run.", code="self_review",
                       status_code=422, title="Invalid seller review")

    duplicate = AppError("You have already rated this store.",
                         code="seller_review_exists", status_code=409,
                         title="Seller review exists")
    already = db.scalar(select(SellerReview.id).where(
        SellerReview.seller_id == seller.id, SellerReview.reviewer_id == reviewer.id))
    if already is not None:
        raise duplicate

    if payload.product_id is not None and db.get(Product, payload.product_id) is None:
        raise NotFoundError("Product not found.")

    review = SellerReview(
        seller_id=seller.id,
        reviewer_id=reviewer.id,
        product_id=payload.product_id,
        accuracy=payload.accuracy,
        order_completeness=payload.order_completeness,
        customer_service=payload.customer_service,
        packaging_quality=payload.packaging_quality,
        overall_rating=payload.overall_rating,
        would_recommend=payload.would_recommend,
        comment=payload.comment,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError as exc:
        # The service check above loses a race; `uq_seller_review_once` does not.
        db.rollback()
        raise duplicate from exc
    db.refresh(review)
    return SellerReviewOut.model_validate(review)


def list_seller_reviews(db: Session, seller_id: uuid.UUID, limit: int) -> list[SellerReviewOut]:
    get_seller_or_404(db, seller_id)
    rows = db.scalars(
        select(SellerReview)
        .where(SellerReview.seller_id == seller_id)
        .order_by(SellerReview.created_at.desc())
        .limit(limit)
    ).all()
    return [SellerReviewOut.model_validate(r) for r in rows]


# ----------------------------------------------------------------- claims

def _claim_out(claim: SellerClaim, seller: Seller | None) -> SellerClaimOut:
    return SellerClaimOut(
        id=claim.id,
        seller_id=claim.seller_id,
        seller_display_name=seller.display_name if seller is not None else None,
        status=claim.status,
        evidence=claim.evidence,
        decision_note=claim.decision_note,
        created_at=claim.created_at,
        decided_at=claim.decided_at,
    )


def submit_claim(db: Session, seller: Seller, user: User,
                 payload: SellerClaimCreate) -> SellerClaimOut:
    if seller.claim_status == SellerClaimStatus.claimed:
        raise AppError("This store has already been claimed.",
                       code="seller_already_claimed", status_code=409,
                       title="Seller already claimed")

    pending = AppError("You already have a claim waiting on this store.",
                       code="claim_pending", status_code=409, title="Claim pending")
    waiting = db.scalar(select(SellerClaim.id).where(
        SellerClaim.seller_id == seller.id,
        SellerClaim.user_id == user.id,
        SellerClaim.status == SellerClaimStatus.pending,
    ))
    if waiting is not None:
        raise pending

    claim = SellerClaim(seller_id=seller.id, user_id=user.id, evidence=payload.evidence)
    db.add(claim)
    try:
        db.commit()
    except IntegrityError as exc:
        # `uq_seller_claim_pending` — the partial index — wins the race.
        db.rollback()
        raise pending from exc
    db.refresh(claim)
    return _claim_out(claim, seller)


def list_pending_claims(db: Session, limit: int) -> list[SellerClaimOut]:
    """Oldest first: a claimant who asked earlier is answered earlier."""
    rows = db.execute(
        select(SellerClaim, Seller)
        .join(Seller, Seller.id == SellerClaim.seller_id)
        .where(SellerClaim.status == SellerClaimStatus.pending)
        .order_by(SellerClaim.created_at)
        .limit(limit)
    ).all()
    return [_claim_out(claim, seller) for claim, seller in rows]


def decide_claim(db: Session, claim_id: uuid.UUID, moderator: User,
                 decision: ClaimDecision) -> SellerClaimOut:
    claim = db.get(SellerClaim, claim_id)
    if claim is None:
        raise NotFoundError("Claim not found.")
    if claim.user_id == moderator.id:
        raise AppError("You cannot decide a claim you submitted.",
                       code="self_decision", status_code=422, title="Invalid decision")
    if claim.status != SellerClaimStatus.pending:
        raise AppError("This claim has already been decided.",
                       code="claim_already_decided", status_code=409,
                       title="Claim already decided")

    # Locked so two moderators approving rival claims at once cannot both win.
    seller = db.get(Seller, claim.seller_id, with_for_update=True)

    if decision.decision == "approve":
        if (seller.claim_status == SellerClaimStatus.claimed
                and seller.claimed_by_id != claim.user_id):
            raise AppError("This store has already been claimed.",
                           code="seller_already_claimed", status_code=409,
                           title="Seller already claimed")
        seller.claimed_by_id = claim.user_id
        seller.claim_status = SellerClaimStatus.claimed
        claim.status = SellerClaimStatus.claimed
    else:
        claim.status = SellerClaimStatus.rejected

    claim.decided_by_id = moderator.id
    claim.decided_at = datetime.now(UTC)
    claim.decision_note = decision.note
    db.commit()
    db.refresh(claim)
    return _claim_out(claim, seller)
