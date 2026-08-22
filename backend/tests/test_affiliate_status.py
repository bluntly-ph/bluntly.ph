"""Provider status -> canonical lifecycle.

Every case here is taken from the owner's real reports or the live Lazada API,
because both providers have a case where the obvious mapping pays out money it
should not.
"""

from __future__ import annotations

import csv
import io
import pathlib

from app.models.enums import AffiliateTxStatus as S
from app.services.affiliate_status import map_lazada, map_shopee, map_status

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


class TestShopee:
    def test_the_ordinary_three(self):
        assert map_shopee({"Order Status": "Completed",
                           "Affiliate Item Status": "Completed"}).status is S.completed
        assert map_shopee({"Order Status": "Pending",
                           "Affiliate Item Status": "Pending"}).status is S.pending
        assert map_shopee({"Order Status": "Cancelled",
                           "Affiliate Item Status": "Cancelled"}).status is S.cancelled

    def test_item_status_beats_order_status(self):
        """The two-row anomaly in the real report.

        Order Status says Completed. The affiliate item says Cancelled, the note
        says "Order is invalid.", and there is a refund. Paying this because the
        *order* completed is paying for a sale the buyer got refunded.
        """
        mapped = map_shopee({
            "Order Status": "Completed",
            "Affiliate Item Status": "Cancelled",
            "Refund Amount(₱)": "474.00",
            "Item Note": "Order is invalid.",
        })
        assert mapped.status is not S.completed
        assert mapped.raw_order_status == "Completed"
        assert mapped.raw_item_status == "Cancelled"

    def test_a_refund_downgrades_a_completed_row(self):
        mapped = map_shopee({"Order Status": "Completed",
                             "Affiliate Item Status": "Completed",
                             "Refund Amount(₱)": "249.00"})
        assert mapped.status is S.returned
        assert "refund" in mapped.reason

    def test_a_refund_never_upgrades(self):
        """Refund evidence may only ever make the outcome worse."""
        mapped = map_shopee({"Order Status": "Pending",
                             "Affiliate Item Status": "Pending",
                             "Refund Amount(₱)": "100.00"})
        assert mapped.status is S.pending

    def test_a_commission_on_a_cancelled_item_is_not_trusted(self):
        """One real row is item-Cancelled, refunded, and still reports 15.12.

        The mapper's job is to classify it as not-money. What the row claims to
        be worth is irrelevant once it is cancelled.
        """
        assert map_shopee({
            "Order Status": "Completed", "Affiliate Item Status": "Cancelled",
            "Refund Amount(₱)": "474.00",
            "Affiliate Net Commission(₱)": "15.12",
        }).status is not S.completed

    def test_an_unknown_status_is_pending_not_completed(self):
        mapped = map_shopee({"Order Status": "Completed",
                             "Affiliate Item Status": "Escrow Released"})
        assert mapped.status is S.pending
        assert "unknown" in mapped.reason

    def test_a_blank_row_is_pending(self):
        assert map_shopee({}).status is S.pending


class TestLazada:
    def test_delivered_rejected_returned(self):
        assert map_lazada({"Status": "Delivered", "Validity": "valid"}).status is S.completed
        assert map_lazada({"Status": "Rejected", "Validity": "invalid"}).status is S.cancelled
        assert map_lazada({"Status": "Returned", "Validity": "valid"}).status is S.returned

    def test_fulfilled_is_pending_not_completed(self):
        """`Fulfilled` appears in the live API and in no export.

        It means shipped, not landed — the order can still be rejected or
        returned. Recognising commission on it would pay for sales that have not
        finished happening.
        """
        assert map_lazada({"Status": "Fulfilled", "Validity": "valid"}).status is S.pending

    def test_returned_wins_over_valid_and_a_positive_payout(self):
        """Ten of eleven real returned rows carry a positive payout, all valid."""
        mapped = map_lazada({"Status": "Returned", "Validity": "valid",
                             "Payout": "75.98", "Returned Time": "2025-06-30"})
        assert mapped.status is S.returned

    def test_validity_valid_cannot_rescue_a_rejection(self):
        """`(Rejected, valid)` occurs in live data — one row in 101."""
        assert map_lazada({"Status": "Rejected", "Validity": "valid"}).status is S.cancelled

    def test_a_return_timestamp_outranks_a_stale_status(self):
        mapped = map_lazada({"Status": "Delivered", "Validity": "valid",
                             "Returned Time": "2025-07-05"})
        assert mapped.status is S.returned
        assert "returned_time" in mapped.reason

    def test_an_unknown_status_is_pending_unless_invalid(self):
        assert map_lazada({"Status": "Shipping", "Validity": "valid"}).status is S.pending
        assert map_lazada({"Status": "Shipping", "Validity": "invalid"}).status is S.cancelled

    def test_payout_alone_never_decides(self):
        assert map_lazada({"Status": "Returned", "Payout": "999.00"}).status is S.returned


class TestAgainstTheRealFiles:
    """The mapper, run over the owner's actual reports."""

    def _rows(self, name, encoding):
        raw = (FIXTURES / name).read_bytes()
        return list(csv.DictReader(io.StringIO(raw.decode(encoding))))

    def test_shopee_report_classifies_every_row(self):
        rows = self._rows("shopee_commission_report.csv", "utf-8-sig")
        assert len(rows) == 108
        counts: dict[S, int] = {}
        for row in rows:
            status = map_shopee(row).status
            counts[status] = counts.get(status, 0) + 1
        # 95 clean completions; 8 pending; 3 cancelled outright; and the 2
        # completed-but-item-cancelled rows land as `returned` on their refunds.
        assert counts[S.completed] == 95
        assert counts[S.pending] == 8
        assert counts.get(S.returned, 0) + counts.get(S.cancelled, 0) == 5
        assert sum(counts.values()) == 108

    def test_lazada_report_classifies_every_row(self):
        rows = self._rows("lazada_conversion_report.csv", "cp1252")
        assert len(rows) == 218
        counts: dict[S, int] = {}
        for row in rows:
            status = map_lazada(row).status
            counts[status] = counts.get(status, 0) + 1
        assert counts[S.completed] == 162   # Delivered
        assert counts[S.cancelled] == 45    # Rejected
        assert counts[S.returned] == 11     # Returned
        assert sum(counts.values()) == 218

    def test_no_real_row_is_left_unclassified(self):
        for name, enc in (("shopee_commission_report.csv", "utf-8-sig"),
                          ("lazada_conversion_report.csv", "cp1252")):
            platform = "shopee" if "shopee" in name else "lazada"
            for row in self._rows(name, enc):
                assert map_status(platform, row).status in set(S)


def test_an_unknown_platform_is_never_money():
    assert map_status("temu", {"Status": "Delivered"}).status is S.pending
