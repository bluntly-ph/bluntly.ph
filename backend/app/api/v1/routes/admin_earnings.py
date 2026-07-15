"""Admin earnings endpoints (M2 slices 6 + 8): commission CSV import and the
manual Honesty Fund distribution trigger. RBAC=moderator; all audit-logged."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import require_role
from app.db.session import get_db
from app.models.user import User
from app.services import commission_service, honesty_fund_service

router = APIRouter(prefix="/admin", tags=["admin: earnings"],
                   dependencies=[Depends(require_role("moderator"))])


class ImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    unmatched: list[int]
    total_rows: int


@router.post("/commissions/import", response_model=ImportResult,
             summary="Import a monthly commission CSV (all-or-nothing, idempotent)")
def import_commissions(file: UploadFile, db: Session = Depends(get_db),
                       mod: User = Depends(require_role("moderator"))) -> ImportResult:
    file_bytes = file.file.read()
    result = commission_service.import_commissions(
        db, mod.id, file.filename or "upload.csv", file_bytes)
    return ImportResult(**result)


class HonestyFundRunRequest(BaseModel):
    # Previous calendar month (Asia/Manila) when omitted.
    cycle_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class HonestyFundRunResult(BaseModel):
    cycle_month: date
    pool: str
    recipients: int
    status: str


@router.post("/honesty-fund/run", response_model=HonestyFundRunResult,
             summary="Run the Honesty Fund distribution for a cycle (idempotent)")
def run_honesty_fund(payload: HonestyFundRunRequest, db: Session = Depends(get_db),
                     mod: User = Depends(require_role("moderator"))) -> HonestyFundRunResult:
    cycle = None
    if payload.cycle_month:
        year, month = (int(part) for part in payload.cycle_month.split("-"))
        if not 1 <= month <= 12:
            raise AppError("cycle_month must be YYYY-MM with a real month.",
                           code="invalid_cycle_month",
                           status_code=422, title="Invalid cycle month")
        cycle = date(year, month, 1)
    result = honesty_fund_service.distribute(db, cycle_month=cycle,
                                             triggered_by=mod.id)
    return HonestyFundRunResult(**result)
