"""Seller service (FR-4).

The rules that decide whether a seller is a duplicate, and what a store's
public numbers say, are plain functions so they are tested on every machine
(`tests/test_seller_rules.py`). The database-backed flow below is tested in
`tests/test_sellers_api.py`.

Two integrity rules carry the weight here, both refusals of self-dealing in the
same shape as `self_report` and Q&A's `cannot_pick_own_answer`:

* a store's claimed owner cannot rate their own store;
* a moderator cannot decide a claim they submitted themselves, nor remove a
  rating of a store they run or a rating they wrote.

Claiming never grants ownership by itself. FR-4 limits seller verification to a
moderator cross-checking the store name against the public listing, so a claim
stays `pending` until a moderator decides it.

Seller reviews publish without the product-review gate (DEVIATIONS §37), so
removal after the fact is the moderation hook, and every public read — the
review list, the summary, the review count in search — filters removed rows.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import MANILA
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.models.enums import Platform, SellerClaimStatus
from app.models.product import Product
from app.models.qa import Answer, Question
from app.models.seller import Seller, SellerClaim, SellerReview
from app.models.user import User
from app.schemas.qa import QAAuthor
from app.schemas.seller import (
    ClaimDecision,
    SellerClaimCreate,
    SellerClaimOut,
    SellerCreate,
    SellerDashboardOut,
    SellerDetailOut,
    SellerOut,
    SellerReviewCreate,
    SellerReviewOut,
    SellerSummary,
    WaitingQuestion,
)

_WHITESPACE = re.compile(r"\s+")

#: The one predicate every public read of seller reviews shares.
_VISIBLE = SellerReview.is_removed.is_(False)


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
    graded dimensions, rounded for display. With no reviews every rate and
    average is None rather than zero — see SellerSummary.
    """
    rows = list(reviews)
    count = len(rows)
    distribution = {star: 0 for star in range(1, 6)}
    for row in rows:
        distribution[row.overall_rating] += 1
    if count == 0:
        return SellerSummary(review_count=0, rating_distribution=distribution)

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
        rating_distribution=distribution,
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
    counts = (
        select(SellerReview.seller_id,
               func.count(SellerReview.id).label("n"),
               func.avg(SellerReview.overall_rating).label("average"))
        .where(_VISIBLE)
        .group_by(SellerReview.seller_id)
        .subquery()
    )
    stmt = select(Seller, func.coalesce(counts.c.n, 0), counts.c.average).outerjoin(
        counts, counts.c.seller_id == Seller.id)
    if platform is not None:
        stmt = stmt.where(Seller.platform == platform)
    if q:
        needle = _WHITESPACE.sub(" ", q).strip().casefold()
        if needle:
            stmt = stmt.where(Seller.normalized_name.contains(needle, autoescape=True))
    stmt = stmt.order_by(Seller.display_name).limit(limit)
    return [
        SellerOut.model_validate(seller).model_copy(update={
            "review_count": n,
            "overall_average": None if average is None else round(float(average), 2),
        })
        for seller, n, average in db.execute(stmt).all()
    ]


def get_seller_detail(db: Session, seller_id: uuid.UUID) -> SellerDetailOut:
    seller = get_seller_or_404(db, seller_id)
    reviews = db.scalars(
        select(SellerReview).where(SellerReview.seller_id == seller.id, _VISIBLE)
    ).all()
    summary = summarize_reviews(reviews)
    data = SellerOut.model_validate(seller).model_dump()
    data["review_count"] = summary.review_count
    data["overall_average"] = summary.overall_average
    return SellerDetailOut(**data, summary=summary)


# ------------------------------------------------------------ dashboard

#: Months of review volume on the owner's dashboard.
DASHBOARD_MONTHS = 6


def monthly_volume(reviews: Iterable[Any], *, months: int = DASHBOARD_MONTHS,
                   today: date | None = None) -> list[dict]:
    """Reviews per Manila calendar month, zero-filled, oldest first.

    A month with no reviews is a zero rather than a missing entry, so a chart
    drawn from this cannot silently close the gap and imply steady volume.
    """
    current = today or datetime.now(MANILA).date()
    keys: list[str] = []
    year, month = current.year, current.month
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    keys.reverse()
    counts = dict.fromkeys(keys, 0)
    for row in reviews:
        local = row.created_at.astimezone(MANILA)
        key = f"{local.year:04d}-{local.month:02d}"
        if key in counts:
            counts[key] += 1
    return [{"month": key, "count": counts[key]} for key in keys]


def _require_owner(seller: Seller, user: User) -> None:
    """The approved owner only. A pending claim is a request, not ownership."""
    if seller.claim_status != SellerClaimStatus.claimed or seller.claimed_by_id != user.id:
        raise ForbiddenError("Only the store's approved owner can open its dashboard.",
                             code="not_store_owner")


def list_my_stores(db: Session, user: User) -> list[SellerDetailOut]:
    """Stores this account runs: claims a moderator approved, nothing pending."""
    stores = db.scalars(
        select(Seller)
        .where(Seller.claimed_by_id == user.id,
               Seller.claim_status == SellerClaimStatus.claimed)
        .order_by(Seller.display_name)
    ).all()
    return [get_seller_detail(db, store.id) for store in stores]


def get_dashboard(db: Session, seller_id: uuid.UUID, user: User) -> SellerDashboardOut:
    """Review monitoring for the store's approved owner (FR-4).

    Everything here is already public on the store page except the waiting
    list's framing: which store questions have no answer from the store yet,
    oldest first, because those are the ones the owner is expected to act on.
    """
    seller = get_seller_or_404(db, seller_id)
    _require_owner(seller, user)

    reviews = db.scalars(
        select(SellerReview).where(SellerReview.seller_id == seller.id, _VISIBLE)
    ).all()
    answered_by_store = select(Answer.question_id).where(Answer.is_seller_answer.is_(True))
    waiting = select(Question).where(
        Question.seller_id == seller.id,
        Question.is_removed.is_(False),
        Question.id.not_in(answered_by_store),
    )
    unanswered = db.scalar(select(func.count()).select_from(waiting.subquery())) or 0
    oldest_first = db.scalars(waiting.order_by(Question.created_at).limit(20)).all()

    return SellerDashboardOut(
        seller=get_seller_detail(db, seller.id),
        monthly_volume=monthly_volume(reviews),
        unanswered_questions=unanswered,
        waiting_questions=[
            WaitingQuestion(id=q.id, body=q.body, created_at=q.created_at)
            for q in oldest_first
        ],
    )


# ---------------------------------------------------------------- reviews

def _review_out(review: SellerReview, reviewer: User | None) -> SellerReviewOut:
    return SellerReviewOut(
        id=review.id,
        seller_id=review.seller_id,
        product_id=review.product_id,
        title=review.title,
        accuracy=review.accuracy,
        order_completeness=review.order_completeness,
        customer_service=review.customer_service,
        packaging_quality=review.packaging_quality,
        overall_rating=review.overall_rating,
        would_recommend=review.would_recommend,
        comment=review.comment,
        photo_urls=list(review.photo_urls or []),
        is_removed=bool(review.is_removed),
        reviewer=QAAuthor.model_validate(reviewer) if reviewer is not None else None,
        created_at=review.created_at,
    )


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
        title=(payload.title or "").strip() or None,
        accuracy=payload.accuracy,
        order_completeness=payload.order_completeness,
        customer_service=payload.customer_service,
        packaging_quality=payload.packaging_quality,
        overall_rating=payload.overall_rating,
        would_recommend=payload.would_recommend,
        comment=payload.comment,
        photo_urls=list(payload.photo_urls),
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError as exc:
        # The service check above loses a race; `uq_seller_review_once` does not.
        db.rollback()
        raise duplicate from exc
    db.refresh(review)
    return _review_out(review, reviewer)


def list_seller_reviews(db: Session, seller_id: uuid.UUID, limit: int) -> list[SellerReviewOut]:
    get_seller_or_404(db, seller_id)
    rows = db.execute(
        select(SellerReview, User)
        .outerjoin(User, User.id == SellerReview.reviewer_id)
        .where(SellerReview.seller_id == seller_id, _VISIBLE)
        .order_by(SellerReview.created_at.desc())
        .limit(limit)
    ).all()
    return [_review_out(review, reviewer) for review, reviewer in rows]


def remove_seller_review(db: Session, review_id: uuid.UUID, moderator: User,
                         note: str | None) -> SellerReviewOut:
    """Take a rating off the store's page and out of its numbers.

    A flag, not a delete: the row stays for the audit trail, and the unique
    constraint keeps the same reviewer from simply posting it again.
    """
    review = db.get(SellerReview, review_id, with_for_update=True)
    if review is None:
        raise NotFoundError("Seller review not found.")
    seller = db.get(Seller, review.seller_id)
    if review.reviewer_id == moderator.id or (
            seller is not None and seller.claimed_by_id == moderator.id):
        raise AppError("You cannot moderate a rating you wrote or a store you run.",
                       code="self_decision", status_code=422, title="Invalid decision")
    if review.is_removed:
        raise AppError("This seller review has already been removed.",
                       code="seller_review_already_removed", status_code=409,
                       title="Seller review already removed")

    review.is_removed = True
    review.removed_at = datetime.now(UTC)
    review.removed_by_id = moderator.id
    review.removal_note = note
    db.commit()
    db.refresh(review)
    reviewer = db.get(User, review.reviewer_id) if review.reviewer_id else None
    return _review_out(review, reviewer)


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
