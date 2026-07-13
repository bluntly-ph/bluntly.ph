"""Health check (Required Endpoint, no auth)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness / identity probe")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        product_id=settings.product_id,
        version=settings.app_version,
        timestamp=datetime.now(UTC),
    )
