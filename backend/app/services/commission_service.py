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
from app.models.review import ReferralLink, Review
from app.models.session import Session as ClickSession
from app.models.user import User
from app.services import report_formats
from app.services.contract_service import reviewer_bps_for_review
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


def _rows_from_bytes(file_bytes: bytes) -> tuple[list, str, list[dict]]:
    """Normalise any supported report into importable rows.

    Real Shopee/Lazada exports are detected and adapted (M3 slice 12); anything
    else falls back to the legacy generic contract from the M2 plan, so existing
    tooling and hand-built CSVs keep working.
    """
    report = report_formats.parse(file_bytes)
    if report.format != "unknown":
        if report.errors:
            raise _invalid(report.errors)
        return report.rows, report.format, report.skipped
    return parse_and_validate(file_bytes), "generic_v1", []


def import_commissions(db: OrmSession, moderator_id: uuid.UUID,
                       filename: str, file_bytes: bytes) -> dict:
    rows, fmt, skipped_rows = _rows_from_bytes(file_bytes)
    tier_bps = _tier_bps(db)
    csv_source = f"{filename}:{hashlib.sha256(file_bytes).hexdigest()[:12]}"

    imported = 0
    skipped_duplicates = 0
    unmatched: list[int] = []

    for row in rows:
        review = None
        session = None
        # 1. Affiliate sub-ID -> referral link -> review. This is the ONLY key the
        #    real marketplace reports echo back, so it is tried first.
        sub_id = getattr(row, "sub_id", None)
        if sub_id:
            link = db.scalar(select(ReferralLink).where(ReferralLink.sub_id == sub_id))
            if link is not None:
                review = db.get(Review, link.review_id)
        # 2. Legacy generic contract: click_ref -> session.
        if review is None and getattr(row, "click_ref", None):
            session = db.scalar(select(ClickSession).where(
                ClickSession.click_ref == row.click_ref))
        # 3. Either format: a previously-recorded order_ref -> session.
        if review is None and session is None and row.order_ref:
            session = db.scalar(select(ClickSession).where(
                ClickSession.order_ref == row.order_ref))
        if review is None and session is not None and session.review_id:
            review = db.get(Review, session.review_id)
        if review is None or review.author_id is None:
            unmatched.append(row.line)  # valid but unattributable — skipped
            continue

        duplicate = db.scalar(select(Commission.id).where(
            Commission.csv_source == csv_source,
            Commission.row_reference == str(row.line)))
        if duplicate is not None:
            skipped_duplicates += 1
            continue

        reviewer = db.get(User, review.author_id)
        tier = tier_bps.get(reviewer.membership_tier, DEFAULT_REVIEWER_BPS)
        # M3 slice 10: the review's contract gates the reviewer's share. No active
        # contract (expired / bought out / never monetized) -> 0 bps, and that
        # share goes to the platform. The Honesty Fund's 30% is untouched.
        bps, contract_status = reviewer_bps_for_review(db, review.id, tier)
        split = split_commission_tiered(row.gross_amount, bps)
        # Cycle date, best source first: the report's own order date, else the
        # click that led to it, else the review's publication. A sub-ID match has
        # no click session at all, so the report must be able to answer this.
        occurred = getattr(row, "occurred_on", None)
        if occurred is None:
            stamp = (session.clicked_at or session.created_at) if session is not None \
                else (review.published_at or review.created_at)
            occurred = stamp.date()
        commission = Commission(
            commission_id=f"com_{uuid.uuid4().hex[:12]}",
            target_type=CommissionTarget.review,
            review_id=review.id,
            session_id=session.id if session is not None else None,
            reviewer_id=reviewer.id,
            reviewer_tier=reviewer.membership_tier,
            reviewer_share_bps=bps,
            contract_status=contract_status,
            currency=row.currency,
            csv_source=csv_source,
            row_reference=str(row.line),
            order_status=row.order_status or None,
            cycle_month=date(occurred.year, occurred.month, 1),
            **split,
        )
        db.add(commission)
        if session is not None:
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
        context={"filename": filename, "csv_source": csv_source, "format": fmt,
                 "total_rows": len(rows), "imported": imported,
                 "skipped_duplicates": skipped_duplicates, "unmatched": unmatched,
                 "skipped_unpayable": len(skipped_rows)},
    ))
    db.commit()
    return {"imported": imported, "skipped_duplicates": skipped_duplicates,
            "unmatched": unmatched, "total_rows": len(rows), "format": fmt,
            # Rows the platform itself says are not payable (pending, cancelled,
            # rejected, returned, invalid, or zero commission). Reported so a
            # moderator can see WHY a big report imported few rows.
            "skipped_unpayable": skipped_rows}


def _award_commission_tokens(db: OrmSession, commission: Commission) -> None:
    """Slice-7 hook: tokens per reconciled commission (idempotent per commission)."""
    from app.core.config import settings
    from app.models.enums import TokenKind
    from app.services.token_service import grant

    if settings.tokens_on_commission > 0 and commission.reviewer_id is not None:
        grant(db, commission.reviewer_id, settings.tokens_on_commission,
              TokenKind.earn_commission, ref_type="commission", ref_id=commission.id)
