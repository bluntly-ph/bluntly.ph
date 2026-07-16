"""Review contract schemas (M3 slice 10)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContractStatus


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_id: uuid.UUID
    reviewer_id: uuid.UUID | None = None
    status: ContractStatus
    started_at: datetime
    term_months: int
    expires_at: datetime
    auto_renew: bool
    renewal_count: int
    buyout_offer_amount: Decimal | None = None
    buyout_offered_at: datetime | None = None
    buyout_accepted_at: datetime | None = None
    buyout_rejected_at: datetime | None = None
    created_at: datetime


class AutoRenewUpdate(BaseModel):
    auto_renew: bool


class BuyoutOffer(BaseModel):
    amount: Decimal = Field(gt=0, description="One-time PHP wallet credit.")
