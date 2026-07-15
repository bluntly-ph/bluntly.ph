"""Commission CSV reconciliation (M2 slice 6, §3.3).

Manual, moderator-driven import of the monthly affiliate-platform export.
All-or-nothing per file: EVERY row is validated before anything is written (no
silent partial success). Idempotent via the (csv_source, row_reference) unique
key, so re-uploading the same file cannot double-count. Runs inline — monthly
exports are small; the Celery task remains a delegation seam for future async use.

CSV contract (header exact, case-insensitive):
    click_ref,order_ref,gross_amount,currency,order_status,platform
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.errors import AppError
from app.models.commission import Commission
from app.models.enums import (
    CommissionTarget,
    ConversionStatus,
    MembershipTier,
    ModerationAction,
)
from app.models.membership import MembershipTierConfig
from app.models.moderation import ModerationLog
from app.models.review import Review
from app.models.session import Session as ClickSession
from app.models.user import User
from app.services.earnings import MAX_REVIEWER_SHARE_BPS, split_commission_tiered

EXPECTED_HEADER = ["click_ref", "order_ref", "gross_amount", "currency",
                   "order_status", "platform"]
VALID_PLATFORMS = {"shopee", "lazada", "amazon"}
DEFAULT_REVIEWER_BPS = 3000


@dataclass
class CsvRow:
    line: int  # 1-based line number in the file (header = line 1)
    click_ref: str
    order_ref: str
    gross_amount: Decimal
    currency: str
    order_status: str
    platform: str


def _invalid(errors: list[dict]) -> AppError:
    return AppError("CSV validation failed; nothing was imported.",
                    code="csv_invalid", status_code=422,
                    title="Invalid commission CSV", extra={"errors": errors})


def parse_and_validate(file_bytes: bytes) -> list[CsvRow]:
    """Parse the whole file; raise 422 with per-line issues if ANY row is bad."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _invalid([{"line": 0, "issue": "file_not_utf8"}]) from exc

    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader]
    if not rows:
        raise _invalid([{"line": 0, "issue": "empty_file"}])

    header = [cell.strip().lower() for cell in rows[0]]
    if header != EXPECTED_HEADER:
        raise _invalid([{"line": 1, "issue": f"bad_header_expected_{','.join(EXPECTED_HEADER)}"}])

    errors: list[dict] = []
    parsed: list[CsvRow] = []
    for i, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue  # blank line
        if len(row) != len(EXPECTED_HEADER):
            errors.append({"line": i, "issue": "wrong_column_count"})
            continue
        click_ref, order_ref, gross_raw, currency, order_status, platform = (
            cell.strip() for cell in row)
        if not click_ref and not order_ref:
            errors.append({"line": i, "issue": "click_ref_or_order_ref_required"})
            continue
        try:
            gross = Decimal(gross_raw)
        except InvalidOperation:
            errors.append({"line": i, "issue": "gross_amount_not_decimal"})
            continue
        if gross <= 0:
            errors.append({"line": i, "issue": "gross_amount_not_positive"})
            continue
        if currency.upper() != "PHP":
            errors.append({"line": i, "issue": "currency_must_be_php"})
            continue
        if platform.lower() not in VALID_PLATFORMS:
            errors.append({"line": i, "issue": "platform_invalid"})
            continue
        parsed.append(CsvRow(line=i, click_ref=click_ref, order_ref=order_ref,
                             gross_amount=gross, currency=currency.upper(),
                             order_status=order_status, platform=platform.lower()))
    if errors:
        raise _invalid(errors)
    return parsed


def _tier_bps(db: OrmSession) -> dict[MembershipTier, int]:
    """Reviewer share bps per tier from config rows; sanity-checked at import."""
    bps = {cfg.code: cfg.revenue_share_bps
           for cfg in db.scalars(select(MembershipTierConfig))}
    bad = {code.value: v for code, v in bps.items()
           if not 0 <= v <= MAX_REVIEWER_SHARE_BPS}
    if bad:
        raise AppError(
            "Tier revenue share config invalid: reviewer bps must be within "
            f"0..{MAX_REVIEWER_SHARE_BPS} (above, the platform share would go negative).",
            code="tier_bps_invalid", status_code=422,
            title="Invalid tier configuration", extra={"tiers": bad})
    return bps


def import_commissions(db: OrmSession, moderator_id: uuid.UUID,
                       filename: str, file_bytes: bytes) -> dict:
    rows = parse_and_validate(file_bytes)
    tier_bps = _tier_bps(db)
    csv_source = f"{filename}:{hashlib.sha256(file_bytes).hexdigest()[:12]}"

    imported = 0
    skipped_duplicates = 0
    unmatched: list[int] = []

    for row in rows:
        session = None
        if row.click_ref:
            session = db.scalar(select(ClickSession).where(
                ClickSession.click_ref == row.click_ref))
        if session is None and row.order_ref:
            session = db.scalar(select(ClickSession).where(
                ClickSession.order_ref == row.order_ref))
        review = db.get(Review, session.review_id) if session and session.review_id else None
        if session is None or review is None or review.author_id is None:
            unmatched.append(row.line)  # valid but unattributable — skipped
            continue

        duplicate = db.scalar(select(Commission.id).where(
            Commission.csv_source == csv_source,
            Commission.row_reference == str(row.line)))
        if duplicate is not None:
            skipped_duplicates += 1
            continue

        reviewer = db.get(User, review.author_id)
        bps = tier_bps.get(reviewer.membership_tier, DEFAULT_REVIEWER_BPS)
        split = split_commission_tiered(row.gross_amount, bps)
        clicked = session.clicked_at or session.created_at
        commission = Commission(
            commission_id=f"com_{uuid.uuid4().hex[:12]}",
            target_type=CommissionTarget.review,
            review_id=review.id,
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewer_tier=reviewer.membership_tier,
            reviewer_share_bps=bps,
            currency=row.currency,
            csv_source=csv_source,
            row_reference=str(row.line),
            order_status=row.order_status or None,
            cycle_month=date(clicked.year, clicked.month, 1),
            **split,
        )
        db.add(commission)
        session.conversion_status = ConversionStatus.converted
        if row.order_ref and not session.order_ref:
            session.order_ref = row.order_ref
        if row.order_status:
            session.order_status = row.order_status
        reviewer.wallet_balance = reviewer.wallet_balance + split["reviewer_share"]
        db.flush()
        _award_commission_tokens(db, commission)
        imported += 1

    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        moderator_id=moderator_id, action=ModerationAction.csv_import,
        context={"filename": filename, "csv_source": csv_source,
                 "total_rows": len(rows), "imported": imported,
                 "skipped_duplicates": skipped_duplicates, "unmatched": unmatched},
    ))
    db.commit()
    return {"imported": imported, "skipped_duplicates": skipped_duplicates,
            "unmatched": unmatched, "total_rows": len(rows)}


def _award_commission_tokens(db: OrmSession, commission: Commission) -> None:
    """Slice-7 hook: tokens per reconciled commission (idempotent per commission)."""
    from app.core.config import settings
    from app.models.enums import TokenKind
    from app.services.token_service import grant

    if settings.tokens_on_commission > 0 and commission.reviewer_id is not None:
        grant(db, commission.reviewer_id, settings.tokens_on_commission,
              TokenKind.earn_commission, ref_type="commission", ref_id=commission.id)
