"""FR-2's independence rule, tested without a database.

"A price range appears only once at least three **independent** observations
exist" is the contractual heart of the price panel, and it lived inside
`get_panel` next to the query — so every test of it required a live Postgres
and skipped everywhere else. Twelve of the 131 skipped tests are in
`test_price_and_compare.py`.

`panel_from` is the same code with the query lifted out. These exercise the
rule itself: what counts as independent, what the panel refuses to say before
the threshold, and the arithmetic once it is met.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import Platform
from app.services.price_service import MIN_INDEPENDENT_OBSERVATIONS, panel_from


class Observation:
    """Duck-typed stand-in for a PriceHistory row."""

    def __init__(self, price, submitted_by=..., observed_at=None,
                 platform=Platform.shopee):
        self.price = Decimal(str(price))
        self.submitted_by = uuid.uuid4() if submitted_by is ... else submitted_by
        self.observed_at = observed_at or date(2026, 8, 1)
        self.platform = platform


def from_distinct_people(*prices):
    return [Observation(p) for p in prices]


class TestTheThresholdCountsPeopleNotRows:

    def test_no_observations_is_insufficient(self):
        panel = panel_from([])
        assert panel.sufficient is False
        assert panel.observation_count == 0
        assert panel.independent_count == 0

    @pytest.mark.parametrize("n", range(1, MIN_INDEPENDENT_OBSERVATIONS))
    def test_below_the_threshold_is_insufficient(self, n):
        panel = panel_from(from_distinct_people(*[100 + i for i in range(n)]))
        assert panel.sufficient is False
        assert panel.independent_count == n

    def test_at_the_threshold_it_opens(self):
        panel = panel_from(from_distinct_people(100, 110, 120))
        assert panel.sufficient is True
        assert panel.independent_count == MIN_INDEPENDENT_OBSERVATIONS

    def test_one_person_reporting_many_times_is_still_one_person(self):
        """The rule the whole feature rests on: a seller cannot manufacture a
        price range by submitting repeatedly."""
        alone = uuid.uuid4()
        rows = [Observation(p, submitted_by=alone) for p in (100, 110, 120, 130, 140)]
        panel = panel_from(rows)
        assert panel.observation_count == 5
        assert panel.independent_count == 1
        assert panel.sufficient is False

    def test_a_deleted_submitter_counts_for_nothing(self):
        """A row with no author cannot be shown to be independent of anything."""
        rows = [Observation(100, submitted_by=None) for _ in range(9)]
        panel = panel_from(rows)
        assert panel.observation_count == 9
        assert panel.independent_count == 0
        assert panel.sufficient is False

    def test_anonymous_rows_do_not_top_up_real_ones(self):
        rows = from_distinct_people(100, 110) + [Observation(120, submitted_by=None)]
        panel = panel_from(rows)
        assert panel.independent_count == 2
        assert panel.sufficient is False


class TestItSaysNothingBeforeTheThreshold:
    """Withholding the numbers is the point, not a UI convenience."""

    @pytest.mark.parametrize("field", ["low", "high", "median", "latest_observed_at"])
    def test_no_price_leaks_while_insufficient(self, field):
        panel = panel_from(from_distinct_people(100, 200))
        assert getattr(panel, field) is None

    def test_the_counts_are_still_reported(self):
        """The UI has to say how many more are needed, so it gets the counts."""
        panel = panel_from(from_distinct_people(100, 200))
        assert panel.observation_count == 2
        assert panel.independent_count == 2


class TestTheArithmeticOnceItOpens:

    def test_low_high_and_median_of_an_odd_count(self):
        panel = panel_from(from_distinct_people(300, 100, 200))
        assert panel.low == Decimal("100")
        assert panel.high == Decimal("300")
        assert panel.median == Decimal("200")

    def test_median_of_an_even_count_is_the_midpoint(self):
        panel = panel_from(from_distinct_people(100, 200, 300, 400))
        assert panel.median == Decimal("250")

    def test_centavos_survive(self):
        panel = panel_from(from_distinct_people("99.99", "100.01", "100.00"))
        assert panel.low == Decimal("99.99")
        assert panel.high == Decimal("100.01")
        assert panel.median == Decimal("100.00")

    def test_identical_prices_give_a_zero_width_range(self):
        panel = panel_from(from_distinct_people(150, 150, 150))
        assert panel.low == panel.high == panel.median == Decimal("150")

    def test_latest_observed_at_is_the_most_recent(self):
        rows = [
            Observation(100, observed_at=date(2026, 1, 1)),
            Observation(110, observed_at=date(2026, 8, 20)),
            Observation(120, observed_at=date(2026, 3, 15)),
        ]
        assert panel_from(rows).latest_observed_at == date(2026, 8, 20)

    def test_platforms_are_deduplicated_and_ordered(self):
        rows = [
            Observation(100, platform=Platform.shopee),
            Observation(110, platform=Platform.lazada),
            Observation(120, platform=Platform.shopee),
        ]
        assert panel_from(rows).platforms == ("lazada", "shopee")


def test_get_panel_still_routes_through_the_rule():
    """The extraction must not have left a second copy behind."""
    import inspect

    from app.services import price_service
    src = inspect.getsource(price_service.get_panel)
    assert "panel_from(rows)" in src, (
        "get_panel no longer delegates to panel_from; the tested rule and the "
        "served one have diverged")
