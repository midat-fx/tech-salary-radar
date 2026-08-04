"""Annualise, convert, judge again — and keep what the board actually quoted."""

from __future__ import annotations

import pytest

from etl.money import (
    NO_PAY,
    Confidence,
    CurrencyGuess,
    Interval,
    PayRange,
    Verdict,
    convert_range,
    to_usd,
)

RATES = {"USD": 1.0, "GBP": 0.79, "EUR": 0.92}


def band(low, high, code="USD", interval=Interval.YEAR):
    return PayRange(low, high, CurrencyGuess(code, Confidence.DECLARED), interval, "test")


class TestToUsd:
    def test_usd_passes_through(self):
        assert to_usd(150_000, "USD", RATES) == 150_000
        assert to_usd(150_000, None, RATES) == 150_000

    def test_a_rate_divides_because_rates_are_units_per_usd(self):
        assert to_usd(79_000, "GBP", RATES) == pytest.approx(100_000)

    def test_a_currency_with_no_rate_yields_nothing_rather_than_the_raw_number(self):
        # Treating an unconvertible figure as USD is how 12,000,000 JPY becomes
        # a twelve-million-dollar salary.
        assert to_usd(12_000_000, "JPY", RATES) is None

    def test_the_code_is_case_insensitive(self):
        assert to_usd(79_000, "gbp", RATES) == pytest.approx(100_000)

    def test_nothing_in_nothing_out(self):
        assert to_usd(None, "GBP", RATES) is None


class TestConvertRange:
    def test_a_plain_usd_band(self):
        result = convert_range(band(150_000, 190_000), RATES)
        assert result.has_salary
        assert result.mid_usd == 170_000
        assert result.judgement.verdict is Verdict.ACCEPTED

    def test_a_gbp_band_is_converted_and_the_original_kept(self):
        result = convert_range(band(79_000, 158_000, code="GBP"), RATES)
        assert result.low_usd == pytest.approx(100_000)
        assert result.high_usd == pytest.approx(200_000)
        # The quoted figures survive so a published number can be traced back
        # without re-running the crawl.
        assert result.currency_original == "GBP"
        assert result.low_original == 79_000
        assert result.interval_original == "year"

    def test_an_hourly_rate_is_annualised_before_conversion(self):
        result = convert_range(band(75, 95, interval=Interval.HOUR), RATES)
        assert result.has_salary
        assert result.mid_usd == pytest.approx((75 + 95) / 2 * 2080)
        assert result.interval_original == "hour"

    def test_a_monthly_euro_band_survives_the_floor(self):
        # The order matters: annualise, then convert, then judge. Judged in any
        # other order this ordinary European salary is thrown away.
        result = convert_range(band(5_000, 6_000, code="EUR", interval=Interval.MONTH), RATES)
        assert result.has_salary
        assert result.mid_usd == pytest.approx((5_000 + 6_000) / 2 * 12 / 0.92)

    def test_a_one_sided_floor_becomes_that_figure(self):
        result = convert_range(band(180_000, None), RATES)
        assert result.has_salary
        assert result.mid_usd == 180_000
        assert result.high_usd is None

    def test_no_range_is_the_shared_empty_result(self):
        assert convert_range(None, RATES) is NO_PAY
        assert not NO_PAY.has_salary
        assert not NO_PAY.dropped

    def test_a_refused_range_keeps_the_original_and_reports_why(self):
        result = convert_range(band(100_000, 900_000), RATES)
        assert not result.has_salary
        assert result.dropped
        assert result.judgement.verdict is Verdict.IMPLAUSIBLE_SPREAD
        assert result.currency_original == "USD"

    def test_dropped_is_not_the_same_as_absent(self):
        # The run report needs to tell "nobody posted a salary" apart from "we
        # found one and refused it"; they mean different things about coverage.
        assert convert_range(None, RATES).dropped is False
        assert convert_range(band(75, 95), RATES).dropped is True

    def test_a_missing_rate_for_a_supported_currency_excludes_the_row(self):
        # The FX cascade fell through to a cache that predates EUR support.
        result = convert_range(band(70_000, 90_000, code="EUR"), {"USD": 1.0})
        assert not result.has_salary
        assert result.judgement.verdict is Verdict.UNSUPPORTED_CURRENCY
        assert result.currency_original == "EUR"

    def test_an_out_of_bounds_figure_is_refused_after_conversion(self):
        result = convert_range(band(5_000_000, 6_000_000), RATES)
        assert not result.has_salary
        assert result.judgement.verdict is Verdict.ABOVE_CEILING


class TestStoredRow:
    def test_an_accepted_row_satisfies_the_writer_invariant(self):
        row = convert_range(band(150_000, 190_000), RATES).to_row()
        assert row["has_salary"] is True
        assert row["salary_mid_usd"] is not None
        assert row["salary_min_usd"] <= row["salary_max_usd"]

    def test_a_refused_row_carries_no_figure_at_all(self):
        # has_salary and salary_mid_usd disagreeing is how a number gets
        # published that no filter on the dashboard explains.
        row = convert_range(band(75, 95), RATES).to_row()
        assert row["has_salary"] is False
        assert row["salary_mid_usd"] is None
        assert row["dropped_oob"] is True

    def test_an_inverted_band_is_stored_the_right_way_round(self):
        # Lever sends the pair straight from a form, and forms get filled in
        # backwards; storing it inverted fails the writer and costs the row.
        row = convert_range(band(190_000, 150_000), RATES).to_row()
        assert row["salary_min_usd"] == 150_000
        assert row["salary_max_usd"] == 190_000

    def test_the_row_carries_exactly_the_salary_columns(self):
        row = convert_range(band(150_000, 190_000), RATES).to_row()
        assert set(row) == {
            "salary_min_usd",
            "salary_max_usd",
            "salary_mid_usd",
            "has_salary",
            "dropped_oob",
            "currency_original",
            "salary_min_orig",
            "salary_max_orig",
            "salary_interval_orig",
        }
