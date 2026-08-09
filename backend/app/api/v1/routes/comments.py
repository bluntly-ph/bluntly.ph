"""Comment routes — reading and posting discussion under a published review.

Visibility is inherited, not re-derived: every path resolves the parent review
through the same publication gate the review routes use, so a comment on an
unpublished draft is unreachable by exactly the people who cannot see the draft.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import get_current_user, get_optional_user
from app.db.session import get_db
from app.models.comment import ReviewComment
from app.models.enums import MemberRole, VoteDirection
from app.models.review import Review
from app.models.user import User
from app.schemas.comment import (
    CommentAuthor,
    CommentCreate,
    CommentOut,
    CommentVoteIn,
)
from app.services import comment_service, review_service

router = APIRouter(tags=["comments"])


def _visible_review_or_404(db: Session, review_id: uuid.UUID,
                           user: User | None) -> Review:
    """The parent review, or 404 — mirrors reviews.py `_visible_or_404`."""
    review = review_service.get_review_or_404(db, review_id)
    is_moderator = user is not None and user.role == MemberRole.moderator
    can_view_unpublished = user is not None and (
        user.id == review.author_id or is_moderator)
    if review.published_at is None and not can_view_unpublished:
        raise NotFoundError("Review not found.", code="review_not_found")
    return review


def _to_out(comment: ReviewComment, authors: dict[uuid.UUID, User],
            my_votes: dict[uuid.UUID, VoteDirection]) -> CommentOut:
    author = authors.get(comment.author_id) if comment.author_id else None
    return CommentOut(
        id=comment.id,
        review_id=comment.review_id,
        parent_id=comment.parent_id,
        # A removed comment keeps its slot in the thread but not its text.
        body=comment_service.REMOVED_PLACEHOLDER if comment.is_removed else comment.body,
        helpful_votes=comment.helpful_votes,
        unhelpful_votes=comment.unhelpful_votes,
        is_removed=comment.is_removed,
        created_at=comment.created_at,
        author=None if comment.is_removed or author is None
        else CommentAuthor.model_validate(author),
        my_vote=my_votes.get(comment.id),
        replies=[],
    )


def _single_out(db: Session, comment: ReviewComment,
                my_vote: VoteDirection | None = None) -> CommentOut:
    """One comment, with its author resolved — the shape every write returns."""
    author = db.get(User, comment.author_id) if comment.author_id else None
    authors = {author.id: author} if author is not None else {}
    return _to_out(comment, authors, {comment.id: my_vote} if my_vote else {})


@router.get("/reviews/{review_id}/comments", response_model=list[CommentOut],
            summary="List the comment thread on a review")
def list_comments(review_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User | None = Depends(get_optional_user)) -> list[CommentOut]:
    review = _visible_review_or_404(db, review_id, user)
    comments, authors, my_votes = comment_service.list_comments(
        db, review, viewer_id=user.id if user else None)

    # Flat rows in, two-level tree out. One pass builds the nodes, a second nests
    # them, so a reply that happens to sort before its parent still lands right.
    nodes = {c.id: _to_out(c, authors, my_votes) for c in comments}
    roots: list[CommentOut] = []
    for comment in comments:
        node = nodes[comment.id]
        parent = nodes.get(comment.parent_id) if comment.parent_id else None
        if parent is None:
            roots.append(node)
        else:
            parent.replies.append(node)
    return roots


@router.post("/reviews/{review_id}/comments", response_model=CommentOut,
             status_code=201, summary="Post a comment or a reply")
def create_comment(review_id: uuid.UUID, payload: CommentCreate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> CommentOut:
    enforce_rate_limit(request, "comment",
                       max_requests=settings.comment_rate_limit_max)
    review = _visible_review_or_404(db, review_id, user)
    comment = comment_service.create_comment(
        db, review, user, payload.body, payload.parent_id)
    return _single_out(db, comment)


@router.delete("/comments/{comment_id}", response_model=CommentOut,
               summary="Remove your comment (or any comment, as a moderator)")
def remove_comment(comment_id: uuid.UUID, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> CommentOut:
    comment = comment_service.get_comment_or_404(db, comment_id)
    _visible_review_or_404(db, comment.review_id, user)
    comment = comment_service.remove_comment(db, comment, user)
    return _single_out(db, comment)


@router.post("/comments/{comment_id}/vote", response_model=CommentOut,
             summary="Cast or change a vote on a comment")
def vote_comment(comment_id: uuid.UUID, payload: CommentVoteIn, request: Request,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> CommentOut:
    enforce_rate_limit(request, "vote", max_requests=settings.vote_rate_limit_max)
    comment = comment_service.get_comment_or_404(db, comment_id)
    _visible_review_or_404(db, comment.review_id, user)
    comment = comment_service.cast_comment_vote(db, comment, user, payload.vote)
    return _single_out(db, comment, payload.vote)


@router.delete("/comments/{comment_id}/vote", response_model=CommentOut,
               summary="Remove your vote from a comment")
def unvote_comment(comment_id: uuid.UUID, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> CommentOut:
    comment = comment_service.get_comment_or_404(db, comment_id)
    _visible_review_or_404(db, comment.review_id, user)
    comment = comment_service.remove_comment_vote(db, comment, user.id)
    return _single_out(db, comment)
