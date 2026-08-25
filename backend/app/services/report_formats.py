"""Real affiliate report formats — Shopee PH and Lazada PH (M3 slice 12).

Owner decision (2026-07-15): **manual CSV is the ingestion path**; a first-party
partnership may replace it later. Marketplace scraping remains ruled out.

The M2 slice-6 plan pinned an *invented* header
(`click_ref,order_ref,gross_amount,currency,order_status,platform`) that no real
export matches. This module reads what the platforms actually produce — see
`docs/AFFILIATE_REPORT_FORMATS.md` for the evidence. Each adapter normalises a
report into `NormalizedRow`s that the existing import service reconciles.

Three things the real files force, all of them money-critical:

1. **Encoding differs.** Shopee is UTF-8-BOM; Lazada is cp1252 (`Pokémon`).
   Demanding UTF-8 rejects a valid Lazada export outright.
2. **Status gates payment.** Shopee rows can be Pending/Cancelled; Lazada rows
   can be Rejected/Returned or `invalid`. Paying those is a real financial error,
   so only settled rows are importable — the rest are *skipped*, never failed.
3. **Zero-commission rows are normal** (~1/3 of both files). They must skip, not
   fail, or the all-or-nothing rule would reject the entire file.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# --- Shopee: Affiliate Commission Report ---------------------------------
SHOPEE_MARKERS = {"order id", "conversion id", "affiliate net commission(₱)"}
SHOPEE_PAYABLE_STATUS = {"completed"}

# --- Lazada: Conversion Report -------------------------------------------
LAZADA_MARKERS = {"conversion time", "check out id", "payout", "validity"}
LAZADA_PAYABLE_STATUS = {"delivered"}
LAZADA_PAYABLE_VALIDITY = {"valid"}


@dataclass
class NormalizedRow:
    """One report row reduced to what reconciliation needs."""

    line: int
    platform: str
    sub_id: str | None       # our identifier, round-tripped via the affiliate link
    order_ref: str | None
    gross_amount: Decimal    # the commission WE receive (not the buyer's spend)
    currency: str
    order_status: str
    # When the order happened, per the report — drives cycle_month. A sub-ID match
    # has no click session to read a date from, so the report must supply it.
    occurred_on: date | None = None
    click_ref: str | None = None   # never present in real exports; kept for symmetry


@dataclass
class ParsedReport:
    format: str
    rows: list[NormalizedRow]          # payable rows only
    skipped: list[dict]                # {line, reason} — reported, never paid
    errors: list[dict]                 # {line, issue} — fail the whole file


def _decode(raw: bytes) -> str:
    """Platform exports are not all UTF-8 — Lazada ships cp1252. Never reject a
    file for encoding: try the real ones in order."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _norm(name: str) -> str:
    return name.strip().lower().replace("﻿", "")


def detect_format(header: list[str]) -> str:
    cols = {_norm(c) for c in header}
    if SHOPEE_MARKERS <= cols:
        return "shopee_commission_report"
    if LAZADA_MARKERS <= cols:
        return "lazada_conversion_report"
    return "unknown"


def _money(value: str) -> Decimal | None:
    cleaned = (value or "").strip().replace(",", "").replace("₱", "")
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(value: str) -> date | None:
    """Shopee: '2026-06-21 20:55:33'. Lazada: '2025-06-30'."""
    raw = (value or "").strip()
    if not raw or raw.upper() in ("N/A", "-"):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _first_sub_id(row: dict, keys: list[str]) -> str | None:
    for k in keys:
        v = (row.get(k) or "").strip()
        # Lazada writes the literal "Unknown" when no sub-id was set.
        if v and v.lower() not in ("unknown", "n/a", "-"):
            return v
    return None


def parse(raw: bytes) -> ParsedReport:
    """Detect the platform and normalise. Never raises on content."""
    reader = csv.reader(io.StringIO(_decode(raw)))
    all_rows = [r for r in reader]
    if not all_rows:
        return ParsedReport("unknown", [], [], [{"line": 0, "issue": "empty_file"}])
    header = all_rows[0]
    fmt = detect_format(header)
    if fmt == "unknown":
        return ParsedReport(fmt, [], [], [{"line": 1, "issue": "unrecognised_report_header"}])

    cols = [_norm(c) for c in header]
    rows, skipped, errors = [], [], []
    for i, values in enumerate(all_rows[1:], start=2):
        if not any(v.strip() for v in values):
            continue
        row = dict(zip(cols, values, strict=False))
        handler = _shopee_row if fmt == "shopee_commission_report" else _lazada_row
        normalized, skip, error = handler(i, row)
        if error:
            errors.append(error)
        elif skip:
            skipped.append(skip)
        elif normalized:
            rows.append(normalized)
    return ParsedReport(fmt, rows, skipped, errors)


def _shopee_row(line: int, row: dict):
    status = (row.get("order Status".lower()) or row.get("order status") or "").strip()
    item_status = (row.get("affiliate item status") or "").strip()
    # Shopee pays only when the order completes — pending commissions can vanish.
    if status.lower() not in SHOPEE_PAYABLE_STATUS:
        return None, {"line": line, "reason": f"order_status={status or 'blank'}"}, None
    if item_status and item_status.lower() not in SHOPEE_PAYABLE_STATUS:
        return None, {"line": line, "reason": f"affiliate_item_status={item_status}"}, None
    amount = _money(row.get("affiliate net commission(₱)")
                    or row.get("total order commission(₱)") or "")
    if amount is None:
        return None, None, {"line": line, "issue": "commission_not_decimal"}
    if amount <= 0:
        return None, {"line": line, "reason": "zero_commission"}, None
    order_ref = (row.get("order id") or "").strip() or None
    sub_id = _first_sub_id(row, ["sub_id1", "sub_id2", "sub_id3", "sub_id4", "sub_id5"])
    if not sub_id and not order_ref:
        return None, None, {"line": line, "issue": "no_sub_id_or_order_id"}
    # Shopee's report has no currency column; the PH program settles in PHP.
    return NormalizedRow(line=line, platform="shopee", sub_id=sub_id,
                         order_ref=order_ref, gross_amount=amount, currency="PHP",
                         order_status=status,
                         occurred_on=_parse_date(row.get("complete time") or "")
                         or _parse_date(row.get("order time") or "")), None, None


def _lazada_row(line: int, row: dict):
    status = (row.get("status") or "").strip()
    validity = (row.get("validity") or "").strip()
    if validity.lower() not in LAZADA_PAYABLE_VALIDITY:
        return None, {"line": line, "reason": f"validity={validity or 'blank'}"}, None
    if status.lower() not in LAZADA_PAYABLE_STATUS:
        return None, {"line": line, "reason": f"status={status or 'blank'}"}, None
    amount = _money(row.get("payout") or "")
    if amount is None:
        return None, None, {"line": line, "issue": "payout_not_decimal"}
    if amount <= 0:
        return None, {"line": line, "reason": "zero_payout"}, None
    currency = (row.get("currency") or "PHP").strip().upper() or "PHP"
    if currency != "PHP":
        return None, None, {"line": line, "issue": "currency_must_be_php"}
    order_ref = ((row.get("check out id") or "").strip()
                 or (row.get("sku order id") or "").strip() or None)
    sub_id = _first_sub_id(row, ["aff sub id", "sub id 1", "sub id 2", "sub id 3",
                                 "sub id 4", "sub id 5", "sub id 6"])
    if not sub_id and not order_ref:
        return None, None, {"line": line, "issue": "no_sub_id_or_order_id"}
    return NormalizedRow(line=line, platform="lazada", sub_id=sub_id,
                         order_ref=order_ref, gross_amount=amount, currency=currency,
                         order_status=status,
                         occurred_on=_parse_date(row.get("conversion time") or "")), None, None


# ---------------------------------------------------------------------------
# Lifecycle parsing
# ---------------------------------------------------------------------------
#
# `parse()` above answers "what can we pay right now", so it DROPS every row
# that is not payable. That is the right question for the legacy one-shot
# import and the wrong one for a lifecycle: a returned order arrives as a
# non-payable row, and dropping it is exactly why a return could never reverse
# the commission it was meant to undo. The order simply vanished from the
# import and its earlier `completed` row stood forever.
#
# `parse_lifecycle()` keeps every row and decides nothing about money. The
# canonical status comes from `affiliate_status`, and what the ledger does
# about a change comes from `affiliate_transitions`.


@dataclass
class LifecycleRow:
    """One provider row, kept whole so the mappers can read it."""

    line: int
    platform: str
    #: Provider-scoped identity. Stable across exports, which is what makes
    #: importing the same order twice from two different files a no-op.
    identity: str
    #: The provider's own row, keys lowercased. `affiliate_status` reads this
    #: directly so provider vocabulary stays in one place.
    raw: dict
    sub_id: str | None
    order_ref: str | None
    gross_amount: Decimal
    currency: str
    occurred_on: date | None = None


@dataclass
class ParsedLifecycle:
    format: str
    rows: list[LifecycleRow]
    #: Rows that could not be given a stable identity. Reported, never guessed
    #: at: an import that invents a key can double-credit on the next file.
    unidentified: list[dict]
    errors: list[dict]


def _clean_cell(row: dict, *names: str) -> str:
    for name in names:
        value = (row.get(name) or "").strip()
        if value:
            return value
    return ""


def shopee_identity(row: dict) -> str | None:
    """A key that is unique per Shopee affiliate item.

    Measured against the owner's 108-row export rather than assumed. `Order id`
    alone collides 29 times, and even Order+Conversion+Item+Model still
    collides 3 times — one group of four rows differing only by `Promotion id`,
    which are promotion splits of a single physical item where only one carries
    commission. Adding `Promotion id` gives 108 distinct keys in 108 rows.
    """
    parts = [
        _clean_cell(row, "order id", "order_id"),
        _clean_cell(row, "conversion id", "conversion_id"),
        _clean_cell(row, "item id", "item_id"),
        _clean_cell(row, "model id", "model_id"),
        _clean_cell(row, "promotion id", "promotion_id"),
    ]
    return "|".join(parts) if any(parts) else None


def lazada_identity(row: dict) -> str | None:
    """Lazada's `Sub Order ID`, which is unique on its own.

    Measured: 218 distinct values in 218 rows of the owner's export. Falls back
    to the SKU/check-out pair only when the column is absent, so an older
    export shape still imports rather than being refused wholesale.
    """
    sub_order = _clean_cell(row, "sub order id", "sub_order_id", "suborder id")
    if sub_order:
        return sub_order
    fallback = [_clean_cell(row, "check out id"), _clean_cell(row, "sku order id")]
    return "|".join(fallback) if any(fallback) else None


_IDENTITY = {
    "shopee_commission_report": ("shopee", shopee_identity),
    "lazada_conversion_report": ("lazada", lazada_identity),
}


def _lifecycle_amount(platform: str, row: dict) -> Decimal:
    """The commission the provider reports for this row, or zero.

    Zero is a legitimate value here, unlike in `parse()`: a cancelled or
    returned row often reports no commission, and it still has to be recorded
    so its lifecycle can be tracked.
    """
    if platform == "shopee":
        raw = _clean_cell(row, "affiliate net commission(₱)",
                          "total order commission(₱)", "affiliate net commission")
    else:
        raw = _clean_cell(row, "payout", "est payout", "estpayout")
    return _money(raw) or Decimal("0")


def parse_lifecycle(raw: bytes) -> ParsedLifecycle:
    """Every row of a provider export, with a stable identity. Never raises."""
    reader = csv.reader(io.StringIO(_decode(raw)))
    all_rows = list(reader)
    if not all_rows:
        return ParsedLifecycle("unknown", [], [], [{"line": 0, "issue": "empty_file"}])

    fmt = detect_format(all_rows[0])
    if fmt not in _IDENTITY:
        return ParsedLifecycle(
            fmt, [], [], [{"line": 1, "issue": "unrecognised_report_header"}])

    platform, identity_of = _IDENTITY[fmt]
    cols = [_norm(c) for c in all_rows[0]]
    rows: list[LifecycleRow] = []
    unidentified: list[dict] = []

    for line, values in enumerate(all_rows[1:], start=2):
        if not any(v.strip() for v in values):
            continue
        row = dict(zip(cols, values, strict=False))
        identity = identity_of(row)
        if not identity:
            unidentified.append({"line": line, "issue": "no_stable_identity"})
            continue

        sub_keys = (["sub_id1", "sub_id2", "sub_id3", "sub_id4", "sub_id5"]
                    if platform == "shopee"
                    else ["aff sub id", "sub id 1", "sub id 2", "sub id 3",
                          "sub id 4", "sub id 5", "sub id 6"])
        date_cell = (_clean_cell(row, "complete time", "order time")
                     if platform == "shopee"
                     else _clean_cell(row, "conversion time", "order time"))

        rows.append(LifecycleRow(
            line=line,
            platform=platform,
            identity=identity,
            raw=row,
            sub_id=_first_sub_id(row, sub_keys),
            order_ref=_clean_cell(row, "order id", "check out id",
                                  "sku order id") or None,
            gross_amount=_lifecycle_amount(platform, row),
            currency="PHP",
            occurred_on=_parse_date(date_cell),
        ))

    return ParsedLifecycle(fmt, rows, unidentified, [])
