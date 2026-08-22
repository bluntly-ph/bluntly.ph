"""Review routes — submission, versioning, AI critique, with the publication gate.

A review is hidden (`published_at IS NULL`) until a moderator publishes it. Anonymous
and other users only see published reviews; authors see their own drafts; moderators
see everything (`?include_unpublished=true`).
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ForbiddenError, NotFoundError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import get_current_user, get_optional_user
from app.db.session import get_db
from app.models.comment import ReviewComment
from app.models.enums import (
    MemberRole,
    ModerationAction,
    ModerationTargetType,
    VoteDirection,
)
from app.models.moderation import ModerationLog
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
from app.services.storage import (
    receipt_key_belongs_to,
    review_photo_belongs_to,
    signed_receipt_url,
    upload_receipt,
    upload_review_photo,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _is_moderator(user: User | None) -> bool:
    return user is not None and user.role == MemberRole.moderator


def _can_view_unpublished(review: Review, user: User | None) -> bool:
    return user is not None and (user.id == review.author_id or _is_moderator(user))


def _visible_or_404(review: Review, user: User | None) -> Review:
    if review.published_at is None and not _can_view_unpublished(review, user):
        raise NotFoundError("Review not found.", code="review_not_found")
    return review


def _own_photo_or_403(url: str | None, user: User) -> str | None:
    """Reject a proof photo this caller did not upload through us.

    Without this the field is self-asserted: any string makes a review
    `verified` (review_service derives it from photo_url being non-null), and
    verified is what unlocks earning eligibility. That would make FR-8's first
    fraud layer free to bypass.
    """
    if url is None or review_photo_belongs_to(url, user.id):
        return url
    raise ForbiddenError(
        "A proof photo must be one you uploaded through /reviews/photo.",
        code="photo_not_owned")


def _own_receipt_key_or_400(key: str | None, user: User) -> str | None:
    """Reject a receipt key this caller did not upload.

    Keys are `{uploader_id}/{uuid}.{ext}`, so without this check a user could
    attach somebody else's receipt to their own review and then read it back
    through the authorized endpoint - which would turn the private bucket into
    a slower version of the hole it replaced.
    """
    if key is None or receipt_key_belongs_to(key, user.id):
        return key
    raise ForbiddenError("That proof of purchase belongs to someone else.",
                         code="receipt_not_owned")


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


def _comment_counts(db: Session, review_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Live comment totals for a set of reviews, in one grouped query (BUG-006).

    Removed comments are excluded: the card's count should match what a reader
    finds when they open the thread, and a soft-deleted comment renders as
    "[removed]" rather than as a contribution.
    """
    if not review_ids:
        return {}
    rows = db.execute(
        select(ReviewComment.review_id, func.count(ReviewComment.id))
        .where(
            ReviewComment.review_id.in_(review_ids),
            ReviewComment.is_removed.is_(False),
        )
        .group_by(ReviewComment.review_id)
    ).all()
    return {review_id: total for review_id, total in rows}


@router.post("", response_model=ReviewOut, status_code=201, summary="Submit a review")
def create_review(payload: ReviewCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ReviewOut:
    _own_photo_or_403(payload.photo_url, user)
    _own_receipt_key_or_400(payload.receipt_key, user)
    review = review_service.create_review(db, user.id, payload)
    return ReviewOut.model_validate(review)


class PhotoUploaded(BaseModel):
    url: str


class ReceiptUploaded(BaseModel):
    """The key is what gets submitted with the review; the URL is for preview.

    Two different things on purpose. `key` is the durable, opaque locator the
    API stores. `preview_url` is a short-lived signed URL so the uploader can
    see what they just attached - it is a bearer credential, expires quickly,
    and is never persisted anywhere.
    """

    key: str
    preview_url: str
    expires_in: int


class ReceiptAccess(BaseModel):
    url: str
    expires_in: int


@router.post("/photo", response_model=PhotoUploaded,
             summary="Upload a PUBLIC review photo; returns its URL")
def upload_photo(file: UploadFile,
                 user: User = Depends(get_current_user)) -> PhotoUploaded:
    """Store a PUBLIC review photo and hand back its URL for `photo_url`.

    Separate from review creation because the photo is picked while the review
    is still being written — there is no review id to attach it to yet, and
    making the author upload only to have submission fail validation would lose
    the file. Declared above `/{review_id}` so the literal path wins the match.

    Proof of purchase does NOT come through here; see POST /reviews/receipt.
    This endpoint writes to a public bucket, which is correct for an image
    that appears on the published review and wrong for anything else.
    """
    return PhotoUploaded(url=upload_review_photo(user.id, file.file.read()))


@router.post("/receipt", response_model=ReceiptUploaded,
             summary="Upload proof of purchase to private storage")
def upload_receipt_route(file: UploadFile,
                         user: User = Depends(get_current_user)) -> ReceiptUploaded:
    """Store proof of purchase and return its private key.

    Separate from /reviews/photo because the two have different audiences, and
    one endpoint returning "a URL suitable for either" is what let a receipt
    end up in a public bucket. The caller does not choose the destination: the
    endpoint it calls decides, server-side.
    """
    key = upload_receipt(user.id, file.file.read())
    ttl = settings.receipt_url_ttl_seconds
    preview = signed_receipt_url(key, ttl)
    if preview is None:
        raise NotFoundError("Upload succeeded but could not be previewed.",
                            code="receipt_not_found")
    return ReceiptUploaded(key=key, preview_url=preview, expires_in=ttl)


@router.get("/{review_id}/receipt", response_model=ReceiptAccess,
            summary="Signed, short-lived access to a review's proof of purchase")
def get_receipt(review_id: uuid.UUID, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> ReceiptAccess:
    """Author or moderator only. Authorization happens before signing.

    404 rather than 403 for everyone else, including when no receipt exists:
    a distinct "forbidden" would confirm to an unrelated user that this review
    has proof of purchase attached, which is itself something they should not
    learn. The PRD scopes receipts to earn_eligible evaluation (FR-3, FR-9),
    so the moderator half of this is a requirement, not a convenience.
    """
    review = review_service.get_review_or_404(db, review_id)
    if not (user.id == review.author_id or _is_moderator(user)):
        raise NotFoundError("Review not found.", code="review_not_found")
    if not review.receipt_key:
        raise NotFoundError("No proof of purchase on this review.",
                            code="receipt_not_found")
    ttl = settings.receipt_url_ttl_seconds
    url = signed_receipt_url(review.receipt_key, ttl)
    if url is None:
        # The row points at an object that is no longer in the bucket.
        raise NotFoundError("No proof of purchase on this review.",
                            code="receipt_not_found")

    # Audit AFTER authorization and AFTER the object is known to exist, so a
    # refused or empty request never writes a successful-access record. Only a
    # moderator is logged: an author opening their own evidence is not a
    # moderation action, and recording it would turn the audit trail into a
    # log of ordinary use.
    if _is_moderator(user) and user.id != review.author_id:
        db.add(ModerationLog(
            log_id=f"mlog_{uuid.uuid4().hex[:10]}",
            moderator_id=user.id,
            action=ModerationAction.receipt_view,
            target_type=ModerationTargetType.review,
            target_ref=review.id,
            # Deliberately no context: the object key, the signed URL and
            # anything off the receipt are exactly what must not be recorded.
        ))
        db.commit()

    return ReceiptAccess(url=url, expires_in=ttl)


@router.get("", response_model=list[ReviewOut],
            summary="List reviews (published; author/mod see more)")
def list_reviews(db: Session = Depends(get_db),
                 user: User | None = Depends(get_optional_user),
                 product_id: uuid.UUID | None = None,
                 include_unpublished: bool = False, limit: int = Query(50, ge=1, le=100),
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
def review_feed(db: Session = Depends(get_db), limit: int = Query(8, ge=1, le=100),
                offset: int = Query(0, ge=0, le=1000),
                product_id: uuid.UUID | None = None,
                author_id: uuid.UUID | None = None, category: str | None = None,
                q: str | None = Query(None, max_length=200),
                sort: Literal["newest", "wilson"] = "wilson",
                mode: Literal["plain", "for-you"] = "plain",
                user: User | None = Depends(get_optional_user)) -> list[FeedItemOut]:
    """The public card feed, and the browsing feed behind `/feed`.

    `mode` defaults to `plain`, which is the behaviour every existing caller
    (landing, search, category, profile) already depends on — sort, slice,
    return. `for-you` is the only thing that ranks:

      * a bounded candidate pool is read at the requested sort,
      * reviews in the reader's chosen categories move to the front,
      * no author or product may take more than two of the visible slots.

    Both extra steps are pure functions in `review_service`, so the ranking is
    testable without a database, and both are no-ops when there is nothing to
    act on: a signed-out reader, or one who skipped onboarding interests, gets
    the same quality-and-recency feed as `plain` rather than an empty one.

    `offset` is bounded at 1000 rather than unbounded: this is a browsing feed,
    not an export.
    """
    if mode == "for-you":
        # Over-read so there is something to thin. Bounded, because a feed page
        # must not turn into a table scan.
        pool = review_service.list_feed(
            db, limit=min(limit * 4, 100), offset=offset, product_id=product_id,
            author_id=author_id, category=category, q=q, sort=sort)
        ranked = review_service.prioritise_interests(
            pool, user.interests if user is not None else None)
        items = review_service.diversify(ranked, limit=min(limit, 100))
    else:
        items = review_service.list_feed(
            db, limit=min(limit, 100), offset=offset, product_id=product_id,
            author_id=author_id, category=category, q=q, sort=sort)
    review_ids = [r.id for r, _, _ in items]
    mine = _my_votes(db, user, review_ids)
    comments = _comment_counts(db, review_ids)
    return [
        FeedItemOut(
            review=_out(r, mine.get(r.id)),
            author=FeedAuthor.model_validate(a) if a is not None else None,
            product=FeedProduct.model_validate(p) if p is not None else None,
            comment_count=comments.get(r.id, 0),
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
        comment_count=_comment_counts(db, [review.id]).get(review.id, 0),
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
    _own_photo_or_403(payload.photo_url, user)
    _own_receipt_key_or_400(payload.receipt_key, user)
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
