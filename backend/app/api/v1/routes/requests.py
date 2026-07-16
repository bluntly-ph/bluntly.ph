"""Request board endpoints (M3 slice 9).

Fulfilment is an explicit claim by the reviewer (`POST /{id}/fulfill`), never an
automatic match on publish — auto-matching a review to a request would be
guesswork, and this pays real tokens.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import RequestStatus
from app.models.user import User
from app.schemas.referral import ReasonRequest
from app.schemas.request_board import FulfillRequest, RequestCreate, RequestOut
from app.services import request_service

router = APIRouter(tags=["request board"])


def _out(req) -> RequestOut:
    out = RequestOut.model_validate(req)
    out.effective_reward = request_service.effective_reward(req)
    return out


@router.post("/requests", response_model=RequestOut, status_code=201,
             summary="Post a review request (AI-screened; bounty escrowed)")
def create_request(payload: RequestCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> RequestOut:
    return _out(request_service.create_request(db, user, payload))


@router.get("/requests", response_model=list[RequestOut], summary="List review requests")
def list_requests(db: Session = Depends(get_db),
                  status: RequestStatus | None = None,
                  sort: Literal["newest", "reward"] = "newest",
                  limit: int = Query(50, ge=1, le=100)) -> list[RequestOut]:
    return [_out(r) for r in request_service.list_requests(db, status, sort, limit)]


@router.get("/requests/{request_id}", response_model=RequestOut, summary="Get a request")
def get_request(request_id: uuid.UUID, db: Session = Depends(get_db)) -> RequestOut:
    return _out(request_service.get_or_404(db, request_id))


@router.post("/requests/{request_id}/upvote", response_model=RequestOut,
             summary="Up-vote a request (raises the platform top-up)")
def upvote(request_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)) -> RequestOut:
    enforce_rate_limit(request, "vote", max_requests=settings.vote_rate_limit_max)
    req = request_service.get_or_404(db, request_id)
    return _out(request_service.upvote(db, req, user))


@router.delete("/requests/{request_id}/upvote", response_model=RequestOut,
               summary="Remove your up-vote")
def remove_upvote(request_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> RequestOut:
    req = request_service.get_or_404(db, request_id)
    return _out(request_service.remove_upvote(db, req, user.id))


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
