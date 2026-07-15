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
from app.models.enums import MemberRole
from app.models.review import Review, ReviewVersion
from app.models.user import User
from app.schemas.ai import CritiqueResponse
from app.schemas.review import ReviewCreate, ReviewOut, ReviewUpdate, ReviewVersionOut, VoteIn
from app.services import review_service, vote_service
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


@router.get("/{review_id}", response_model=ReviewOut, summary="Get a review")
def get_review(review_id: uuid.UUID, db: Session = Depends(get_db),
               user: User | None = Depends(get_optional_user)) -> ReviewOut:
    review = _visible_or_404(review_service.get_review_or_404(db, review_id), user)
    return ReviewOut.model_validate(review)


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
    return ReviewOut.model_validate(review)


@router.delete("/{review_id}/vote", response_model=ReviewOut,
               summary="Remove your helpfulness vote from a review")
def unvote_review(review_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ReviewOut:
    review = review_service.get_review_or_404(db, review_id)
    review = vote_service.remove_vote(db, review, user.id)
    return ReviewOut.model_validate(review)


@router.post("/{review_id}/critique", response_model=CritiqueResponse,
             summary="AI critique of a stored review (author or moderator)")
def critique_review(review_id: uuid.UUID, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)) -> CritiqueResponse:
    review = review_service.get_review_or_404(db, review_id)
    if review.author_id != user.id and user.role != MemberRole.moderator:
        raise ForbiddenError("Only the author or a moderator may critique this review.",
                             code="not_review_owner")
    return get_provider().critique(review.title, review.discussion)
