"""Review routes — submission, versioning, AI critique, with the publication gate.

A review is hidden (`published_at IS NULL`) until a moderator publishes it. Anonymous
and other users only see published reviews; authors see their own drafts; moderators
see everything (`?include_unpublished=true`).
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ForbiddenError, NotFoundError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import get_current_user, get_optional_user
from app.db.session import get_db
from app.models.enums import MemberRole, ModerationTargetType, VoteDirection
from app.models.product import Product
from app.models.review import Review, ReviewVersion
from app.models.user import User
from app.models.vote import ReviewVote
from app.schemas.ai import CritiqueResponse
from app.schemas.report import ReportCreate, ReportOut
from app.schemas.review import (
    FeedAuthor,
    FeedItemOut,
    FeedProduct,
    ReviewCreate,
    ReviewOut,
    ReviewUpdate,
    ReviewVersionOut,
    VoteIn,
)
from app.services import report_service, review_service, vote_service
from app.services.ai_critique import get_provider

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _is_moderator(user: User | None) -> bool:
    return user is not None and user.role == MemberRole.moderator


def _can_view_unpublished(review: Review, user: User | None) -> bool:
    return user is not None and (user.id == review.author_id or _is_moderator(user))


def _visible_or_404(review: Review, user: User | None) -> Review:
    if review.published_at is None and not _can_view_unpublished(review, user):
        raise NotFoundError("Review not found.", code="review_not_found")
    return review


def _my_votes(db: Session, user: User | None,
              review_ids: list[uuid.UUID]) -> dict[uuid.UUID, VoteDirection]:
    """The viewer's own votes across a set of reviews, in one query (BUG-013).

    Batched deliberately: the feed returns up to 100 rows, and asking per row
    would turn one page render into 100 extra round trips against a database in
    another region. Signed-out readers cost nothing — no viewer, no query.
    """
    if user is None or not review_ids:
        return {}
    rows = db.execute(
        select(ReviewVote.review_id, ReviewVote.vote).where(
            ReviewVote.voter_id == user.id,
            ReviewVote.review_id.in_(review_ids),
        )
    ).all()
    return {review_id: vote for review_id, vote in rows}


def _out(review: Review, my_vote: VoteDirection | None = None) -> ReviewOut:
    out = ReviewOut.model_validate(review)
    out.my_vote = my_vote
    return out


@router.post("", response_model=ReviewOut, status_code=201, summary="Submit a review")
def create_review(payload: ReviewCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ReviewOut:
    review = review_service.create_review(db, user.id, payload)
    return ReviewOut.model_validate(review)


@router.get("", response_model=list[ReviewOut],
            summary="List reviews (published; author/mod see more)")
def list_reviews(db: Session = Depends(get_db),
                 user: User | None = Depends(get_optional_user),
                 product_id: uuid.UUID | None = None,
                 include_unpublished: bool = False, limit: int = 50,
                 sort: Literal["newest", "wilson"] = "newest") -> list[ReviewOut]:
    stmt = select(Review).where(Review.is_removed.is_(False))
    if product_id is not None:
        stmt = stmt.where(Review.product_id == product_id)
    if _is_moderator(user) and include_unpublished:
        pass  # moderators may see everything
    elif user is not None:
        stmt = stmt.where(or_(Review.published_at.isnot(None), Review.author_id == user.id))
    else:
        stmt = stmt.where(Review.published_at.isnot(None))
    if sort == "wilson":
        stmt = stmt.order_by(Review.wilson_score.desc(), Review.created_at.desc())
    else:
        stmt = stmt.order_by(Review.created_at.desc())
    rows = db.scalars(stmt.limit(limit))
    return [ReviewOut.model_validate(r) for r in rows]


# Declared before "/{review_id}" so "feed" is matched as this route rather than
# being parsed as a review UUID (which would 422).
@router.get("/feed", response_model=list[FeedItemOut],
            summary="Public feed: published reviews joined with author + product")
def review_feed(db: Session = Depends(get_db), limit: int = 8,
                product_id: uuid.UUID | None = None,
                author_id: uuid.UUID | None = None, category: str | None = None,
                q: str | None = None,
                sort: Literal["newest", "wilson"] = "wilson",
                user: User | None = Depends(get_optional_user)) -> list[FeedItemOut]:
    items = review_service.list_feed(db, limit=min(limit, 100), product_id=product_id,
                                     author_id=author_id, category=category, q=q, sort=sort)
    mine = _my_votes(db, user, [r.id for r, _, _ in items])
    return [
        FeedItemOut(
            review=_out(r, mine.get(r.id)),
            author=FeedAuthor.model_validate(a) if a is not None else None,
            product=FeedProduct.model_validate(p) if p is not None else None,
        )
        for r, a, p in items
    ]


@router.get("/{review_id}", response_model=ReviewOut, summary="Get a review")
def get_review(review_id: uuid.UUID, db: Session = Depends(get_db),
               user: User | None = Depends(get_optional_user)) -> ReviewOut:
    review = _visible_or_404(review_service.get_review_or_404(db, review_id), user)
    return _out(review, _my_votes(db, user, [review.id]).get(review.id))


@router.get("/{review_id}/full", response_model=FeedItemOut,
            summary="A review with its author + product (respects the publication gate)")
def get_review_full(review_id: uuid.UUID, db: Session = Depends(get_db),
                    user: User | None = Depends(get_optional_user)) -> FeedItemOut:
    review = _visible_or_404(review_service.get_review_or_404(db, review_id), user)
    author = db.get(User, review.author_id) if review.author_id is not None else None
    product = db.get(Product, review.product_id)
    return FeedItemOut(
        review=_out(review, _my_votes(db, user, [review.id]).get(review.id)),
        author=FeedAuthor.model_validate(author) if author is not None else None,
        product=FeedProduct.model_validate(product) if product is not None else None,
    )


@router.patch("/{review_id}", response_model=ReviewOut,
              summary="Edit a review (creates a new version)")
def update_review(review_id: uuid.UUID, payload: ReviewUpdate,
                  db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ReviewOut:
    review = review_service.get_review_or_404(db, review_id)
    if review.author_id != user.id and user.role != MemberRole.moderator:
        raise ForbiddenError("Only the author or a moderator may edit this review.",
                             code="not_review_owner")
    review = review_service.update_review(db, review, user.id, payload)
    return ReviewOut.model_validate(review)


@router.get("/{review_id}/versions", response_model=list[ReviewVersionOut],
            summary="List a review's version history")
def list_versions(review_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User | None = Depends(get_optional_user)) -> list[ReviewVersionOut]:
    review = review_service.get_review_or_404(db, review_id)
    _visible_or_404(review, user)
    return [ReviewVersionOut.model_validate(v) for v in review_service.list_versions(db, review_id)]


@router.get("/{review_id}/versions/{version_number}", response_model=ReviewVersionOut,
            summary="Get a specific review version")
def get_version(review_id: uuid.UUID, version_number: int, db: Session = Depends(get_db),
                user: User | None = Depends(get_optional_user)) -> ReviewVersionOut:
    _visible_or_404(review_service.get_review_or_404(db, review_id), user)
    version = db.scalar(select(ReviewVersion).where(
        ReviewVersion.review_id == review_id,
        ReviewVersion.version_number == version_number))
    if version is None:
        raise NotFoundError("Review version not found.", code="version_not_found")
    return ReviewVersionOut.model_validate(version)


@router.post("/{review_id}/vote", response_model=ReviewOut,
             summary="Cast or change a helpfulness vote on a published review")
def vote_review(review_id: uuid.UUID, payload: VoteIn, request: Request,
                db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> ReviewOut:
    enforce_rate_limit(request, "vote", max_requests=settings.vote_rate_limit_max)
    review = review_service.get_review_or_404(db, review_id)
    review = vote_service.cast_vote(db, review, user, payload.vote)
    # Echo the vote just cast rather than re-reading it: the client uses this
    # response to set its pressed state, so it must not come back empty.
    return _out(review, payload.vote)


@router.delete("/{review_id}/vote", response_model=ReviewOut,
               summary="Remove your helpfulness vote from a review")
def unvote_review(review_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ReviewOut:
    review = review_service.get_review_or_404(db, review_id)
    review = vote_service.remove_vote(db, review, user.id)
    # The vote is gone, so my_vote is None — the schema default, stated here so
    # the symmetry with the POST above is visible rather than inferred.
    return _out(review, None)


@router.post("/{review_id}/report", response_model=ReportOut, status_code=201,
             summary="Report a published review to the moderators")
def report_review(review_id: uuid.UUID, payload: ReportCreate, request: Request,
                  db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ReportOut:
    # Same 60s bucket shape as voting: reporting is a community action and the
    # limiter is what stops one account from carpet-reporting a reviewer.
    enforce_rate_limit(request, "report", max_requests=settings.report_rate_limit_max)
    review = review_service.get_review_or_404(db, review_id)
    # Only reportable once visible — an unpublished draft is already in the
    # moderator queue, and 404ing keeps drafts unenumerable by non-authors.
    _visible_or_404(review, user)
    log, _created = report_service.file_report(
        db,
        reporter_id=user.id,
        author_id=review.author_id,
        target_type=ModerationTargetType.review,
        target_ref=review.id,
        reason=payload.reason,
        notes=payload.notes,
        evidence_url=payload.evidence_url,
    )
    # A repeat report returns 201 with the original row: the reporter's intent is
    # satisfied either way, and telling them "already reported" leaks nothing.
    return ReportOut.model_validate(log)


@router.post("/{review_id}/critique", response_model=CritiqueResponse,
             summary="AI critique of a stored review (author or moderator)")
def critique_review(review_id: uuid.UUID, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)) -> CritiqueResponse:
    review = review_service.get_review_or_404(db, review_id)
    if review.author_id != user.id and user.role != MemberRole.moderator:
        raise ForbiddenError("Only the author or a moderator may critique this review.",
                             code="not_review_owner")
    return get_provider().critique(review.title, review.discussion)
