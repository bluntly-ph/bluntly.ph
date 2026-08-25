"""Lazada conversion fetching: month splitting, pagination, dedupe, and PII.

None of these need a database, so unlike most of the affiliate suite they run
on every machine rather than only in CI.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.adapters import lazada

# --- month splitting -------------------------------------------------------

def test_a_single_month_is_one_window():
    assert lazada.month_windows(date(2026, 8, 1), date(2026, 8, 31)) == [
        (date(2026, 8, 1), date(2026, 8, 31))
    ]


def test_a_range_crossing_a_month_splits_and_clips():
    """Lazada answers "only support fetch single month data" to a multi-month
    request, so a quarter would return an error rather than three months of
    rows. Windows are clipped to the caller's bounds: a range starting on the
    17th begins on the 17th, not the 1st."""
    assert lazada.month_windows(date(2026, 8, 17), date(2026, 9, 3)) == [
        (date(2026, 8, 17), date(2026, 8, 31)),
        (date(2026, 9, 1), date(2026, 9, 3)),
    ]


def test_a_range_crossing_a_year_rolls_over_correctly():
    """December + 1 month is January of the NEXT year — the arithmetic most
    likely to be wrong, and it would silently fetch the wrong twelve months."""
    assert lazada.month_windows(date(2026, 12, 20), date(2027, 1, 10)) == [
        (date(2026, 12, 20), date(2026, 12, 31)),
        (date(2027, 1, 1), date(2027, 1, 10)),
    ]


def test_a_quarter_becomes_three_windows():
    assert len(lazada.month_windows(date(2026, 6, 1), date(2026, 8, 31))) == 3


def test_a_single_day_is_still_one_window():
    assert lazada.month_windows(date(2026, 8, 5), date(2026, 8, 5)) == [
        (date(2026, 8, 5), date(2026, 8, 5))
    ]


def test_an_inverted_range_asks_for_nothing():
    """Better to fetch nothing than to loop, or to quietly swap the bounds and
    return a range the caller did not ask for."""
    assert lazada.month_windows(date(2026, 9, 1), date(2026, 8, 1)) == []


def test_windows_never_overlap_and_leave_no_gap():
    windows = lazada.month_windows(date(2026, 1, 15), date(2026, 12, 20))
    for (_, end), (nxt, _) in zip(windows, windows[1:], strict=False):
        assert (nxt - end).days == 1, "windows overlap or skip a day"


# --- fetching, pagination, dedupe -----------------------------------------

def _row(sub_order: str, status: str = "Delivered") -> dict:
    return {"orderId": f"O{sub_order}", "subOrderId": sub_order,
            "status": status, "estPayout": "10.00"}


@pytest.fixture
def calls(monkeypatch):
    """Record every API call and serve canned pages."""
    recorded: list[dict] = []
    pages: dict[tuple[str, int], list[dict]] = {}

    def fake_call(path, params):
        recorded.append(params)
        key = (params["dateStart"], params["page"])
        return {"data": {"list": pages.get(key, [])}}

    monkeypatch.setattr(lazada, "_call", fake_call)
    monkeypatch.setattr(lazada.settings, "lazada_user_token", "t", raising=False)
    return recorded, pages


def test_a_multi_month_range_makes_one_call_per_month(calls):
    recorded, pages = calls
    pages[("2026-08-17", 1)] = [_row("A")]
    pages[("2026-09-01", 1)] = [_row("B")]

    out = lazada.fetch_conversions(date(2026, 8, 17), date(2026, 9, 3), page_size=50)

    starts = [c["dateStart"] for c in recorded]
    assert starts == ["2026-08-17", "2026-09-01"]
    # Neither call may span months, which is the whole point.
    for call in recorded:
        assert call["dateStart"][:7] == call["dateEnd"][:7]
    assert {c.sub_order_id for c in out} == {"A", "B"}


def test_pagination_is_followed_within_a_month(calls):
    recorded, pages = calls
    pages[("2026-08-01", 1)] = [_row(str(i)) for i in range(2)]
    pages[("2026-08-01", 2)] = [_row("last")]

    out = lazada.fetch_conversions(date(2026, 8, 1), date(2026, 8, 31), page_size=2)

    assert [c["page"] for c in recorded] == [1, 2]
    assert len(out) == 3


def test_the_same_sub_order_seen_twice_is_merged(calls):
    """Windows do not overlap, but a row's status can change between calls. The
    later sighting is the provider's more recent word about the same sub-order,
    so it wins — and the row must not be counted twice."""
    recorded, pages = calls
    pages[("2026-08-01", 1)] = [_row("DUP", status="Delivered")]
    pages[("2026-09-01", 1)] = [_row("DUP", status="Returned")]

    out = lazada.fetch_conversions(date(2026, 8, 1), date(2026, 9, 30), page_size=50)

    assert len(out) == 1, "the same sub-order was counted twice"
    assert out[0].status == "Returned"


def test_a_row_with_no_sub_order_id_is_not_silently_dropped(calls):
    """It cannot be deduplicated, but losing a sale is worse than keeping a
    row that might be a duplicate."""
    _, pages = calls
    pages[("2026-08-01", 1)] = [{"orderId": "O1", "status": "Delivered"},
                                {"orderId": "O2", "status": "Delivered"}]
    assert len(lazada.fetch_conversions(
        date(2026, 8, 1), date(2026, 8, 31), page_size=50)) == 2


# --- buyer identity --------------------------------------------------------

@pytest.mark.parametrize("field", [
    "memberEmail", "memberName", "memberId", "member_email", "member_id",
    "Member Email", "buyerEmail", "buyerName", "buyer_id", "phone", "mobile",
])
def test_buyer_identity_never_enters_a_conversion(field):
    """`raw` is persisted verbatim into affiliate_postbacks.raw, so anything
    that reaches a Conversion is one ordinary code path away from the database.
    The ledger needs to know a sale happened, never who bought."""
    conversion = lazada._as_conversion({
        "orderId": "O1", "subOrderId": "S1", "status": "Delivered", field: "secret",
    })
    assert field not in conversion.raw
    assert "secret" not in str(conversion.raw)


def test_scrubbing_keeps_everything_the_ledger_needs():
    conversion = lazada._as_conversion({
        "orderId": "O1", "subOrderId": "S1", "status": "Delivered",
        "estPayout": "12.00", "productName": "Keyboard", "memberEmail": "b@e.com",
    })
    assert conversion.sub_order_id == "S1"
    assert conversion.est_payout == "12.00"
    assert conversion.raw["productName"] == "Keyboard"
    assert "memberEmail" not in conversion.raw
