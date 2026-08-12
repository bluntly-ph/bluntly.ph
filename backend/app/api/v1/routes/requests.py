"""Request board endpoints (M3 slice 9).

Fulfilment is an explicit claim by the reviewer (`POST /{id}/fulfill`), never an
automatic match on publish — auto-matching a review to a request would be
guesswork, and this pays real tokens.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import get_current_user, get_optional_user, require_role
from app.db.session import get_db
from app.models.enums import RequestStatus
from app.models.request_board import RequestUpvote
from app.models.user import User
from app.schemas.referral import ReasonRequest
from app.schemas.request_board import FulfillRequest, RequestCreate, RequestOut
from app.services import request_service

router = APIRouter(tags=["request board"])


def _out(req, my_upvote: bool = False) -> RequestOut:
    out = RequestOut.model_validate(req)
    out.my_upvote = my_upvote
    return out


def _my_upvotes(db: Session, user: User | None,
                request_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Which of these requests the viewer has up-voted, in one query (BUG-026).

    Batched for the same reason as review votes: the board lists up to 100 rows
    and a per-row check would multiply the round trips by 100.
    """
    if user is None or not request_ids:
        return set()
    return set(db.scalars(
        select(RequestUpvote.request_id).where(
            RequestUpvote.user_id == user.id,
            RequestUpvote.request_id.in_(request_ids),
        )
    ).all())


@router.post("/requests", response_model=RequestOut, status_code=201,
             summary="Post a review request (AI-screened; free to post)")
def create_request(payload: RequestCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> RequestOut:
    return _out(request_service.create_request(db, user, payload))


@router.get("/requests", response_model=list[RequestOut], summary="List review requests")
def list_requests(db: Session = Depends(get_db),
                  status: RequestStatus | None = None,
                  sort: Literal["newest", "demand"] = "newest",
                  limit: int = Query(50, ge=1, le=100),
                  user: User | None = Depends(get_optional_user)) -> list[RequestOut]:
    rows = request_service.list_requests(db, status, sort, limit)
    mine = _my_upvotes(db, user, [r.id for r in rows])
    return [_out(r, r.id in mine) for r in rows]


@router.get("/requests/{request_id}", response_model=RequestOut, summary="Get a request")
def get_request(request_id: uuid.UUID, db: Session = Depends(get_db),
                user: User | None = Depends(get_optional_user)) -> RequestOut:
    req = request_service.get_or_404(db, request_id)
    return _out(req, req.id in _my_upvotes(db, user, [req.id]))


@router.post("/requests/{request_id}/upvote", response_model=RequestOut,
             summary="Up-vote a request (says you want this reviewed too)")
def upvote(request_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)) -> RequestOut:
    enforce_rate_limit(request, "vote", max_requests=settings.vote_rate_limit_max)
    req = request_service.get_or_404(db, request_id)
    # True by construction: upvote() raises rather than returning un-voted.
    return _out(request_service.upvote(db, req, user), True)


@router.delete("/requests/{request_id}/upvote", response_model=RequestOut,
               summary="Remove your up-vote")
def remove_upvote(request_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> RequestOut:
    req = request_service.get_or_404(db, request_id)
    return _out(request_service.remove_upvote(db, req, user.id), False)


@router.post("/requests/{request_id}/fulfill", response_model=RequestOut,
             summary="Claim a request with your own published review")
def fulfill(request_id: uuid.UUID, payload: FulfillRequest,
            db: Session = Depends(get_db),
            user: User = Depends(get_current_user)) -> RequestOut:
    req = request_service.get_or_404(db, request_id)
    return _out(request_service.fulfill(db, req, user, payload.review_id))


@router.delete("/requests/{request_id}", response_model=RequestOut,
               summary="Cancel your open request (refunds the escrow)")
def cancel(request_id: uuid.UUID, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)) -> RequestOut:
    req = request_service.get_or_404(db, request_id)
    return _out(request_service.cancel_request(db, req, user))


@router.post("/admin/requests/{request_id}/remove", response_model=RequestOut,
             summary="Remove a request (moderator; refunds the requester)")
def admin_remove(request_id: uuid.UUID, payload: ReasonRequest,
                 db: Session = Depends(get_db),
                 mod: User = Depends(require_role("moderator"))) -> RequestOut:
    req = request_service.get_or_404(db, request_id)
    return _out(request_service.remove_request(db, req, mod.id, payload.reason))
