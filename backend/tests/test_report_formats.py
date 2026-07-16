"""Real Shopee/Lazada report ingestion (M3 slice 12).

The fixtures in tests/fixtures/ are REAL owner-supplied exports, byte-for-byte
(including Lazada's cp1252 encoding and Shopee's BOM). They are the whole point:
the M2 importer was written against an invented header that no export matches, so
only the real files can prove ingestion works.
"""

from __future__ import annotations

import pathlib
import uuid as _uuid
from decimal import Decimal

import pytest

from app.services import report_formats
from tests.conftest import register_and_token, requires_db
from tests.test_commissions_api import _import, ensure_tier_configs

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SHOPEE = FIXTURES / "shopee_commission_report.csv"
LAZADA = FIXTURES / "lazada_conversion_report.csv"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------- pure parsing
def test_lazada_report_is_not_utf8_and_still_parses():
    """The real Lazada export is cp1252 ('Pokémon'). Demanding UTF-8 — as the M2
    importer did — rejects a perfectly valid file."""
    raw = LAZADA.read_bytes()
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")
    report = report_formats.parse(raw)
    assert report.format == "lazada_conversion_report"
    assert report.errors == []
    assert report.rows


def test_shopee_report_detected_and_normalised():
    report = report_formats.parse(SHOPEE.read_bytes())
    assert report.format == "shopee_commission_report"
    assert report.errors == []
    # Every payable row: real money, PHP, a settled status.
    for row in report.rows:
        assert row.gross_amount > 0
        assert row.currency == "PHP"
        assert row.order_status.lower() == "completed"
        assert row.order_ref
        assert row.occurred_on is not None


def test_lazada_only_valid_and_delivered_rows_are_payable():
    report = report_formats.parse(LAZADA.read_bytes())
    for row in report.rows:
        assert row.order_status.lower() == "delivered"
        assert row.gross_amount > 0
        assert row.currency == "PHP"
    # The report genuinely contains unpayable rows; they must be skipped, not lost.
    reasons = " ".join(s["reason"] for s in report.skipped)
    assert "validity=invalid" in reasons
    assert "zero_payout" in reasons


def test_pending_and_cancelled_rows_are_never_payable():
    """Paying a pending or cancelled order is a real financial error: Shopee only
    pays once an order completes."""
    report = report_formats.parse(SHOPEE.read_bytes())
    reasons = " ".join(s["reason"] for s in report.skipped)
    assert "order_status=Pending" in reasons
    assert "order_status=Cancelled" in reasons
    assert not [r for r in report.rows if r.order_status.lower() != "completed"]


def test_zero_commission_rows_skip_rather_than_fail_the_file():
    """~1/3 of both reports earn 0. Under all-or-nothing, treating those as
    invalid would reject the entire upload."""
    for path in (SHOPEE, LAZADA):
        report = report_formats.parse(path.read_bytes())
        assert report.errors == []
        assert any("zero" in s["reason"] for s in report.skipped)


def test_purchase_value_is_not_mistaken_for_commission():
    """Shopee's `Purchase Value(₱)` is the BUYER's spend; our commission is
    `Affiliate Net Commission(₱)`. Confusing them would overpay enormously."""
    report = report_formats.parse(SHOPEE.read_bytes())
    total = sum(r.gross_amount for r in report.rows)
    # The real file's commissions are ~PHP 1.3k against ~PHP 100k of purchases.
    assert total < Decimal("5000")


def test_unrecognised_header_is_rejected():
    report = report_formats.parse(b"foo,bar\n1,2\n")
    assert report.format == "unknown"
    assert report.errors[0]["issue"] == "unrecognised_report_header"


def test_real_reports_carry_no_sub_id_today():
    """Documents the attribution blocker with evidence: neither real export has a
    populated sub-ID, so every row is unattributable until links carry one."""
    for path in (SHOPEE, LAZADA):
        report = report_formats.parse(path.read_bytes())
        assert all(r.sub_id is None for r in report.rows)


# ------------------------------------------------------- end-to-end ingestion
@requires_db
def test_real_shopee_report_imports_via_sub_id(client):
    """The fix end-to-end: a link carrying our sub-ID makes a real report row
    attributable, and the reviewer gets paid."""
    from app.db.session import SessionLocal
    from app.models.review import ReferralLink
    from app.services.referral_service import sub_id_for_review
    from tests.test_commissions_api import make_click

    ensure_tier_configs()
    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah, mh = _auth(author_token), _auth(mod_token)
    rid, _, author_id = make_click(client, ah, mh, name=f"SubId-{_uuid.uuid4().hex[:6]}")

    # The moderator's link was generated with the review's sub-ID.
    expected_sub = sub_id_for_review(_uuid.UUID(rid))
    db = SessionLocal()
    try:
        link = db.scalar(select_link(ReferralLink, rid))
        assert link.sub_id == expected_sub
    finally:
        db.close()

    # Take a real Shopee row and put our sub-ID in Sub_id1.
    raw = SHOPEE.read_bytes().decode("utf-8-sig").splitlines()
    header = raw[0].split(",")
    sub_idx = [i for i, c in enumerate(header) if c.strip().lower() == "sub_id1"][0]
    payable = None
    for line in raw[1:]:
        cells = next(__import__("csv").reader([line]))
        if len(cells) == len(header) and cells[1].strip().lower() == "completed":
            cells[sub_idx] = expected_sub
            payable = cells
            break
    assert payable is not None
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(header)
    w.writerow(payable)
    resp = _import(client, mh, buf.getvalue(), filename=f"shopee_{_uuid.uuid4().hex[:6]}.csv")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["format"] == "shopee_commission_report"
    assert body["imported"] == 1, f"sub-ID match should attribute the row: {body}"
    assert body["unmatched"] == []


@requires_db
def test_real_report_without_sub_id_is_unmatched_not_paid(client):
    """Today's reports carry no sub-ID: every row must land in `unmatched` — never
    paid to the wrong person, never silently dropped."""
    ensure_tier_configs()
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    resp = _import(client, mh, LAZADA.read_bytes().decode("cp1252"),
                   filename=f"lazada_{_uuid.uuid4().hex[:6]}.csv")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["format"] == "lazada_conversion_report"
    assert body["imported"] == 0
    assert len(body["unmatched"]) == body["total_rows"] > 0
    assert body["skipped_unpayable"]      # the invalid/returned/zero rows


def select_link(model, review_id: str):
    from sqlalchemy import select
    return select(model).where(model.review_id == _uuid.UUID(review_id),
                               model.status == "active")
