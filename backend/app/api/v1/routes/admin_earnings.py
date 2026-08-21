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
from app.services import commission_service, honesty_fund_service, retention_service

router = APIRouter(prefix="/admin", tags=["admin: earnings"],
                   dependencies=[Depends(require_role("moderator"))])


class ImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    unmatched: list[int]
    total_rows: int
    # Which report format was detected: shopee_commission_report |
    # lazada_conversion_report | generic_v1.
    format: str = "generic_v1"
    # Rows the platform says aren't payable yet (pending/cancelled/rejected/
    # returned/invalid/zero commission) — skipped, never paid.
    skipped_unpayable: list[dict] = Field(default_factory=list)


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


class RetentionSweepResult(BaseModel):
    #: IPs replaced by a salted hash at the 30-day mark.
    hashed: int
    #: Hashes deleted and user agents purged at 90 days, counted together —
    #: `run_retention_sweep` sums them, and this mirrors what it returns rather
    #: than inventing a shape it does not produce.
    purged: int


@router.post("/pii-retention/run", response_model=RetentionSweepResult,
             summary="Run the sessions PII retention sweep (idempotent)")
def run_pii_retention(db: Session = Depends(get_db),
                      mod: User = Depends(require_role("moderator"))
                      ) -> RetentionSweepResult:
    """Apply the 30/90-day retention schedule to `sessions`, on demand.

    The sweep is scheduled in `celery_app.beat_schedule` for 03:00 daily, and
    nothing runs it: the deployment is two Vercel services, frontend and
    backend, with no worker and no beat, and the broker points at a Redis that
    is not configured. Measured on 2026-08-21, three sessions were already
    holding a raw IP past their 30-day hashing deadline, and the 90-day
    deletions begin falling due from late October.

    So this exists for the same reason the Honesty Fund has a manual trigger:
    the retention schedule is a promise the platform makes about people's data,
    and it should not depend on infrastructure that is not deployed. Idempotent
    - the sweep selects on deadlines, so running it twice is a no-op the second
    time.
    """
    counts = retention_service.run_retention_sweep(db)
    return RetentionSweepResult(**counts)
