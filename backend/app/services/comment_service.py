"""Comment threads on published reviews (BUG-014).

Visibility follows the review: a comment is readable exactly when the review it
hangs off is readable, so this module never re-implements the publication gate —
callers hand it a review they have already resolved through
`review_service.get_review_or_404` + the route's `_visible_or_404`.

Removal is soft. A removed comment keeps its row and its position in the thread
but surrenders its body, so replies underneath it still make sense.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.models.comment import ReviewComment, ReviewCommentVote
from app.models.enums import MemberRole, VoteDirection
from app.models.product import Product
from app.models.review import Review
from app.models.user import User

# What a removed comment says instead of its body. The row stays so the thread
# shape survives; the text does not.
REMOVED_PLACEHOLDER = "[removed]"


def _commentable_or_404(review: Review) -> None:
    """Only a live, published review accepts comments."""
    if review.published_at is None or review.is_removed:
        raise NotFoundError("Review not found.", code="review_not_found")


def get_comment_or_404(db: Session, comment_id: uuid.UUID) -> ReviewComment:
    comment = db.get(ReviewComment, comment_id)
    if comment is None:
        raise NotFoundError("Comment not found.", code="comment_not_found")
    return comment


def create_comment(db: Session, review: Review, author: User, body: str,
                   parent_id: uuid.UUID | None = None) -> ReviewComment:
    _commentable_or_404(review)

    if parent_id is not None:
        parent = get_comment_or_404(db, parent_id)
        if parent.review_id != review.id:
            # Guessing a parent id from another review would otherwise graft a
            # thread onto the wrong page.
            raise NotFoundError("Comment not found.", code="comment_not_found")
        if parent.parent_id is not None:
            raise AppError(
                "Replies are one level deep — reply to the top comment instead.",
                code="comment_nesting_too_deep", status_code=409,
                title="Conflicting state")
        if parent.is_removed:
            raise AppError("That comment was removed.",
                           code="comment_removed", status_code=409,
                           title="Conflicting state")

    comment = ReviewComment(
        review_id=review.id, author_id=author.id, parent_id=parent_id, body=body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def remove_comment(db: Session, comment: ReviewComment, user: User) -> ReviewComment:
    """Soft-delete. The author may retract; a moderator may remove anyone's."""
    if comment.author_id != user.id and user.role != MemberRole.moderator:
        raise ForbiddenError(
            "Only the author or a moderator may remove this comment.",
            code="not_comment_owner")
    comment.is_removed = True
    db.commit()
    db.refresh(comment)
    return comment


def list_comments(db: Session, review: Review,
                  viewer_id: uuid.UUID | None = None
                  ) -> tuple[list[ReviewComment], dict[uuid.UUID, User],
                             dict[uuid.UUID, VoteDirection]]:
    """Every comment on a review, oldest first, with authors and the viewer's votes.

    Authors and votes are fetched in one query each rather than per comment —
    a 50-comment thread would otherwise be 100 round trips.
    """
    comments = list(db.scalars(
        select(ReviewComment)
        .where(ReviewComment.review_id == review.id)
        .order_by(ReviewComment.created_at.asc())
    ))
    if not comments:
        return [], {}, {}

    author_ids = {c.author_id for c in comments if c.author_id is not None}
    authors: dict[uuid.UUID, User] = {}
    if author_ids:
        authors = {
            u.id: u for u in db.scalars(select(User).where(User.id.in_(author_ids)))
        }

    my_votes: dict[uuid.UUID, VoteDirection] = {}
    if viewer_id is not None:
        comment_ids = [c.id for c in comments]
        my_votes = {
            comment_id: vote
            for comment_id, vote in db.execute(
                select(ReviewCommentVote.comment_id, ReviewCommentVote.vote).where(
                    ReviewCommentVote.comment_id.in_(comment_ids),
                    ReviewCommentVote.voter_id == viewer_id,
                )
            )
        }
    return comments, authors, my_votes


def recompute_comment_vote_aggregates(db: Session, comment: ReviewComment) -> None:
    """Refresh the counters from the vote rows, in the vote's own transaction."""
    votes = list(db.scalars(
        select(ReviewCommentVote.vote).where(
            ReviewCommentVote.comment_id == comment.id)
    ))
    comment.helpful_votes = sum(1 for v in votes if v == VoteDirection.up)
    comment.unhelpful_votes = len(votes) - comment.helpful_votes


def cast_comment_vote(db: Session, comment: ReviewComment, voter: User,
                      direction: VoteDirection) -> ReviewComment:
    if comment.is_removed:
        raise AppError("That comment was removed.", code="comment_removed",
                       status_code=409, title="Conflicting state")
    if comment.author_id == voter.id:
        raise AppError("You cannot vote on your own comment.",
                       code="cannot_vote_own_comment", status_code=409,
                       title="Conflicting state")

    existing = db.scalar(select(ReviewCommentVote).where(
        ReviewCommentVote.comment_id == comment.id,
        ReviewCommentVote.voter_id == voter.id))
    if existing is None:
        db.add(ReviewCommentVote(
            comment_id=comment.id, voter_id=voter.id, vote=direction))
    else:
        existing.vote = direction
    try:
        db.flush()
    except IntegrityError as exc:  # concurrent first-votes hit the unique index
        db.rollback()
        raise AppError("Your vote was submitted twice at once; retry.",
                       code="vote_conflict", status_code=409,
                       title="Conflicting state") from exc

    recompute_comment_vote_aggregates(db, comment)
    db.commit()
    db.refresh(comment)
    return comment


def remove_comment_vote(db: Session, comment: ReviewComment,
                        voter_id: uuid.UUID) -> ReviewComment:
    existing = db.scalar(select(ReviewCommentVote).where(
        ReviewCommentVote.comment_id == comment.id,
        ReviewCommentVote.voter_id == voter_id))
    if existing is None:
        raise NotFoundError("You have no vote on this comment.",
                            code="vote_not_found")
    db.delete(existing)
    db.flush()
    recompute_comment_vote_aggregates(db, comment)
    db.commit()
    db.refresh(comment)
    return comment


def list_authored(db: Session, author_id: uuid.UUID, *, limit: int = 24,
                  offset: int = 0) -> list[tuple[ReviewComment, Review, str | None, int]]:
    """A member's own comments, newest first, each with its parent review.

    The profile's Comments tab reads this. Three filters make it a *public*
    list rather than a personal one: the comment is not removed, the review is
    not removed, and the review is published. A member's profile is readable by
    anyone, so a comment on their own unpublished draft must not leak through it.

    The reply count is counted in the same statement rather than per row — the
    N+1 the review feed already learned to avoid (BUG-006).
    """
    comment_count = (
        select(func.count(ReviewComment.id))
        .where(
            ReviewComment.review_id == Review.id,
            ReviewComment.is_removed.is_(False),
        )
        .correlate(Review)
        .scalar_subquery()
    )
    rows = db.execute(
        select(ReviewComment, Review, Product.canonical_name, comment_count)
        .join(Review, Review.id == ReviewComment.review_id)
        .outerjoin(Product, Product.id == Review.product_id)
        .where(
            ReviewComment.author_id == author_id,
            ReviewComment.is_removed.is_(False),
            Review.is_removed.is_(False),
            Review.published_at.is_not(None),
        )
        .order_by(ReviewComment.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [(row[0], row[1], row[2], row[3]) for row in rows]
