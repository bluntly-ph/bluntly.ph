"""Public referral attribution redirect: GET /r/{review_id}.

Root-mounted (shareable URL), no auth required. Records a `sessions` click row with
the PII retention schedule, then 302s to the affiliate URL. The raw affiliate URL is
never exposed elsewhere — this redirect is the only way out, so clicks are always
attributed.
"""

from __future__ import annotations

import ipaddress
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.security import get_optional_user
from app.db.session import get_db
from app.models.enums import EarnEligibleStatus
from app.models.review import Review
from app.models.user import User
from app.services import referral_service

router = APIRouter(tags=["referral"])


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    raw = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    try:
        return str(ipaddress.ip_address(raw)) if raw else None
    except ValueError:
        return None  # e.g. TestClient's "testclient" host — not a real IP


@router.get("/r/{review_id}", summary="Referral attribution redirect (public)")
def referral_redirect(review_id: uuid.UUID, request: Request,
                      db: Session = Depends(get_db),
                      user: User | None = Depends(get_optional_user)) -> RedirectResponse:
    review = db.get(Review, review_id)
    if (review is None or review.is_removed or review.published_at is None
            or review.earn_eligible_status != EarnEligibleStatus.monetized):
        raise NotFoundError("No active referral link for this review.",
                            code="referral_not_found")
    link = referral_service.get_active_link(db, review_id)
    if link is None:
        raise NotFoundError("No active referral link for this review.",
                            code="referral_not_found")
    destination = referral_service.record_click(
        db, review, link, user_id=(user.id if user else None),
        user_agent=request.headers.get("user-agent"), ip_address=_client_ip(request),
    )
    return RedirectResponse(destination, status_code=302)
