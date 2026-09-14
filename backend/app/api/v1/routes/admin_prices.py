"""Price observation moderation (FR-2, FR-9) — moderator only.

Every community price starts pending, and the public price panel is built from
approved ones alone (`price_service.panel_from`). This router is where they are
decided. The service refuses a moderator deciding a price they submitted.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.product import PriceObservationDecision, PriceObservationQueueItem
from app.services import price_service

router = APIRouter(prefix="/admin/price-observations", tags=["admin"],
                   dependencies=[Depends(require_role("moderator"))])


@router.get("", response_model=list[PriceObservationQueueItem],
            summary="Price observations waiting for a decision, oldest first")
def pending_observations(db: Session = Depends(get_db),
                         product_id: uuid.UUID | None = None,
                         limit: int = Query(50, ge=1, le=200)) -> list[PriceObservationQueueItem]:
    return price_service.list_pending(db, product_id=product_id, limit=limit)


@router.post("/{observation_id}/decision", response_model=PriceObservationQueueItem,
             summary="Approve or reject a price observation")
def decide_observation(observation_id: uuid.UUID, decision: PriceObservationDecision,
                       db: Session = Depends(get_db),
                       moderator: User = Depends(get_current_user)) -> PriceObservationQueueItem:
    return price_service.decide_observation(db, observation_id, moderator, decision)
