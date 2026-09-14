"""External integrity provider status (FR-8 layers 2 and 3) — moderator only.

Tells a moderator whether plagiarism and reverse image checks can run at all,
so an empty result is never mistaken for a pass.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import require_role
from app.services.integrity_checks import ProviderStatusOut, provider_status

router = APIRouter(prefix="/admin/integrity-providers", tags=["admin"],
                   dependencies=[Depends(require_role("moderator"))])


@router.get("", response_model=ProviderStatusOut,
            summary="Whether plagiarism and reverse image checks can run")
def integrity_providers() -> ProviderStatusOut:
    settings = get_settings()
    return provider_status(plagiarism_provider=settings.plagiarism_provider,
                           reverse_image_provider=settings.reverse_image_provider)
