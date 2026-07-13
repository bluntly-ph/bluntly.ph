"""Ad-hoc AI critique route (M1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.ai import CritiqueRequest, CritiqueResponse
from app.services.ai_critique import get_provider

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/critique", response_model=CritiqueResponse,
             summary="AI critique of arbitrary draft review text")
def critique(payload: CritiqueRequest,
             _: User = Depends(get_current_user)) -> CritiqueResponse:
    return get_provider().critique(payload.title, payload.text)
