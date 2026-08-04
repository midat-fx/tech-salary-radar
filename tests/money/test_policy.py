"""Whether a parsed range is believable, and the reason when it is not."""

from __future__ import annotations

import pytest

from etl.config import SALARY_MAX_USD, SALARY_MIN_USD
from etl.money import (
    MAX_SPREAD,
    PRE_CONVERSION_FLOOR,
    Confidence,
    CurrencyGuess,
    Interval,
    PayRange,
    Verdict,
    confidence_penalty,
    judge_annual_usd,
    judge_parsed,
    midpoint,
)


def band(low, high, code="USD", interval=Interval.YEAR, confidence=Confidence.ASSUMED):
    return PayRange(low, high, CurrencyGuess(code, confidence), interval, "test")


class TestMidpoint:
    def test_a_two_sided_range_contributes_its_middle(self):
        assert midpoint(150_000, 190_000) == 170_000

    def test_a_floor_with_no_ceiling_contributes_the_floor(self):
        # "from $180,000" is a commitment. Averaging it with an invented ceiling
        # would manufacture precision; dropping it would lose the senior tail.
        assert midpoint(180_000, None) == 180_000
        assert midpoint(None, 180_000) == 180_000

    def test_nothing_in_gives_nothing_out(self):
        assert midpoint(None, None) is None


class TestJudgeParsed:
    def test_an_ordinary_band_is_accepted(self):
        assert judge_parsed(band(150_000, 190_000)).verdict is Verdict.ACCEPTED

    def test_no_range_is_empty_rather_than_rejected(self):
        # Most postings have no salary at all; that is not a parser failure and
        # must not be counted as one.
        assert judge_parsed(None).verdict is Verdict.EMPTY
        assert judge_parsed(band(None, None)).verdict is Verdict.EMPTY

    def test_a_zero_band_is_refused(self):
        # Boards do send 0 - 0 to mean "not disclosed".
        assert judge_parsed(band(0, 0)).verdict is Verdict.NON_POSITIVE
        assert judge_parsed(band(-5, 100_000)).verdict is Verdict.NON_POSITIVE

    def test_a_currency_with_no_rate_is_excluded_not_guessed(self):
        verdict = judge_parsed(band(8_000_000, 12_000_000, code="JPY"))
        assert verdict.verdict is Verdict.UNSUPPORTED_CURRENCY
        assert "JPY" in verdict.detail

    def test_a_band_too_wide_to_be_one_band_is_refused(self):
        # Base paired with total compensation, or a salary matched against equity.
        assert judge_parsed(band(100_000, 100_000 * (MAX_SPREAD + 1))).verdict is (
            Verdict.IMPLAUSIBLE_SPREAD
        )

    def test_a_band_exactly_at_the_spread_limit_is_kept(self):
        assert judge_parsed(band(50_000, 50_000 * MAX_SPREAD)).accepted

    def test_a_one_sided_range_has_no_spread_to_judge(self):
        assert judge_parsed(band(180_000, None)).accepted

    def test_an_hourly_rate_read_as_annual_falls_below_the_floor(self):
        # "$75 - $95" with the interval missed annualises to $75, which is what
        # the pre-conversion floor exists to catch.
        assert judge_parsed(band(75, 95)).verdict is Verdict.BELOW_FLOOR

    def test_the_same_rate_with_its_interval_read_correctly_is_kept(self):
        assert judge_parsed(band(75, 95, interval=Interval.HOUR)).accepted

    def test_a_monthly_european_band_is_judged_after_annualising(self):
        # EUR 5,000-6,000/month is an ordinary salary; judged monthly it looks
        # like a rounding error.
        assert judge_parsed(band(5_000, 6_000, code="EUR", interval=Interval.MONTH)).accepted

    def test_the_floor_is_applied_to_the_annualised_figure(self):
        assert PRE_CONVERSION_FLOOR == 1_000
        assert judge_parsed(band(400, 900)).verdict is Verdict.BELOW_FLOOR


class TestJudgeAnnualUsd:
    def test_an_ordinary_figure_is_accepted(self):
        assert judge_annual_usd(170_000, 150_000, 190_000).accepted

    def test_below_the_configured_floor_is_refused(self):
        verdict = judge_annual_usd(SALARY_MIN_USD - 1, None, None)
        assert verdict.verdict is Verdict.BELOW_FLOOR

    def test_above_the_configured_ceiling_is_refused(self):
        # A funding round or a total-contract value that survived anchoring.
        verdict = judge_annual_usd(SALARY_MAX_USD + 1, None, None)
        assert verdict.verdict is Verdict.ABOVE_CEILING

    def test_the_bounds_themselves_are_accepted(self):
        assert judge_annual_usd(SALARY_MIN_USD, None, None).accepted
        assert judge_annual_usd(SALARY_MAX_USD, None, None).accepted

    def test_a_post_conversion_blow_up_is_caught(self):
        # Survives this far only when the bounds were converted at different
        # rates, i.e. the currencies were mixed upstream.
        assert judge_annual_usd(500_000, 100_000, 900_000).verdict is Verdict.IMPLAUSIBLE_SPREAD

    def test_nothing_to_judge_is_empty(self):
        assert judge_annual_usd(None, None, None).verdict is Verdict.EMPTY


class TestOneSetOfThresholds:
    def test_the_spread_rule_is_the_same_before_and_after_conversion(self):
        # These used to be 3x in one place and 20x in another, so a posting was
        # kept or dropped by which board it came from.
        wide = band(100_000, 100_000 * (MAX_SPREAD + 0.5))
        assert judge_parsed(wide).verdict is Verdict.IMPLAUSIBLE_SPREAD
        assert judge_annual_usd(
            midpoint(wide.low, wide.high), wide.low, wide.high
        ).verdict is Verdict.IMPLAUSIBLE_SPREAD

    def test_every_verdict_carries_a_reason_except_the_ordinary_ones(self):
        assert judge_parsed(band(8_000_000, 9_000_000, code="JPY")).detail
        assert judge_parsed(band(75, 95)).detail
        assert judge_parsed(None).detail == ""


class TestConfidencePenalty:
    def test_an_assumed_currency_is_flagged_as_weaker_evidence(self):
        assert confidence_penalty(band(150_000, 190_000, confidence=Confidence.ASSUMED))

    def test_a_declared_currency_is_not(self):
        assert not confidence_penalty(
            band(150_000, 190_000, code="GBP", confidence=Confidence.DECLARED)
        )


@pytest.mark.parametrize("verdict", list(Verdict))
def test_every_verdict_value_is_distinct_and_readable(verdict):
    # The values become counter names in the run report, so they have to be
    # stable strings rather than enum repr.
    assert verdict.value == verdict.value.lower()
    assert " " not in verdict.value
