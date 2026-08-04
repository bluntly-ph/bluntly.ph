"""Public marketplace postback receiver: GET /api/v1/postback/lazada.

Public by necessity — Lazada calls it from their infrastructure, so it cannot sit
behind our auth. It is authenticated by a shared secret in the query string and
it creates **no money**; see app/services/postback_service.py for why that
separation is load-bearing rather than cautious.

Always answers 200 to a correctly-authenticated call, including for payloads it
cannot attribute. Lazada's troubleshooting guide is explicit that a non-2xx (or a
server that validates their mock 'Run Test' values) reads as a broken
integration, and there is nothing the caller could do about a bad payload anyway.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_db
from app.services import postback_service

router = APIRouter(prefix="/postback", tags=["postback"])


@router.get("/lazada", summary="Lazada order postback (public, shared-secret auth)")
def lazada_postback(request: Request, db: Session = Depends(get_db)) -> dict:
    if not settings.lazada_postback_enabled:
        raise AppError("Postback receiver is not configured.",
                       code="postback_disabled", status_code=503,
                       title="Not configured")

    # Accepts both the short (?t=&c=&o=...) and long (?token=&click_ref=...) forms;
    # the short one exists only to shrink what a human pastes into Adsense.
    params = postback_service.normalize(dict(request.query_params))
    if not postback_service.secret_ok(params.pop("token", None)):
        # Deliberately terse: a probe learns only that it guessed wrong.
        raise AppError("Invalid postback token.", code="postback_forbidden",
                       status_code=403, title="Forbidden")

    # Their 'Run Test' sends mock test_XXX values. Acknowledge, write nothing.
    if postback_service.is_test_fire(params):
        return {"status": "ok", "mode": "test"}

    return postback_service.record_lazada_postback(db, params)
