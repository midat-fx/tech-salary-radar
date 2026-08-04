"""The posted range as a value: ordering, spread, annualisation, description."""

from __future__ import annotations

import pytest

from etl.money import Confidence, CurrencyGuess, Interval, PayRange


def band(low, high, code="USD", interval=Interval.YEAR, origin="test"):
    return PayRange(low, high, CurrencyGuess(code, Confidence.DECLARED), interval, origin)


class TestOrdering:
    def test_an_inverted_pair_is_stored_the_right_way_round(self):
        assert (band(190_000, 150_000).low, band(190_000, 150_000).high) == (150_000, 190_000)

    def test_an_already_ordered_pair_is_left_alone(self):
        assert (band(150_000, 190_000).low, band(150_000, 190_000).high) == (150_000, 190_000)

    def test_a_one_sided_range_has_nothing_to_reorder(self):
        assert band(180_000, None).low == 180_000
        assert band(None, 180_000).high == 180_000


class TestShape:
    def test_empty_one_sided_and_full_are_distinguishable(self):
        assert band(None, None).is_empty
        assert band(180_000, None).is_one_sided
        assert not band(150_000, 190_000).is_one_sided
        assert not band(150_000, 190_000).is_empty

    def test_spread_is_the_ratio_of_the_bounds(self):
        assert band(100_000, 400_000).spread == pytest.approx(4.0)

    def test_a_range_with_one_bound_has_no_spread(self):
        assert band(180_000, None).spread is None
        assert band(None, None).spread is None

    def test_a_zero_floor_has_no_spread_rather_than_infinity(self):
        assert band(0, 100_000).spread is None


class TestAnnualise:
    def test_it_scales_both_bounds_and_marks_the_interval_yearly(self):
        annual = band(5_000, 6_000, interval=Interval.MONTH).annualised()
        assert (annual.low, annual.high) == (60_000, 72_000)
        assert annual.interval is Interval.YEAR

    def test_it_is_idempotent_once_yearly(self):
        yearly = band(150_000, 190_000)
        assert yearly.annualised() is yearly
        assert yearly.annualised().annualised().low == 150_000

    def test_it_keeps_the_currency_and_the_origin(self):
        annual = band(75, 95, code="GBP", interval=Interval.HOUR, origin="description").annualised()
        assert annual.currency.code == "GBP"
        assert annual.origin == "description"

    def test_a_one_sided_range_annualises_its_one_bound(self):
        assert band(5_000, None, interval=Interval.MONTH).annualised().low == 60_000


class TestDescribe:
    def test_it_names_the_figures_the_unit_and_where_it_came_from(self):
        line = band(150_000, 190_000, origin="description").describe()
        assert "150,000..190,000" in line
        assert "USD/year" in line
        assert "description" in line

    def test_a_missing_bound_shows_as_a_dash_not_as_none(self):
        assert "180,000..-" in band(180_000, None).describe()

    def test_the_confidence_is_visible_because_it_changes_what_the_figure_means(self):
        assert "declared" in band(150_000, 190_000).describe()
