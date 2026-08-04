"""Pay periods: reading one out of an ad, and the multipliers that annualise it."""

from __future__ import annotations

import pytest

from etl.money import DAYS_PER_YEAR, MULTIPLIER, Interval, detect_interval, to_annual


class TestDetect:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("$75 - $95 per hour", Interval.HOUR),
            ("$75/hour", Interval.HOUR),
            ("hourly rate of $80", Interval.HOUR),
            ("£600 per day", Interval.DAY),
            ("£600 day rate", Interval.DAY),
            ("$3,000 per week", Interval.WEEK),
            ("€5.000 per month", Interval.MONTH),
            ("€5.000 monthly", Interval.MONTH),
            ("5 000 ₸ в месяц", Interval.MONTH),
            ("$150,000 per annum", Interval.YEAR),
            ("$150,000 annually", Interval.YEAR),
        ],
    )
    def test_the_wordings_boards_use(self, text, expected):
        assert detect_interval(text) is expected

    def test_an_unqualified_figure_is_yearly(self):
        # What an unqualified range means on these boards. The cost of the
        # default is asymmetric and deliberate: a missed hourly rate becomes an
        # absurd annual figure that the floor throws away, which is a silent
        # loss rather than a wrong number.
        assert detect_interval("$150,000 - $180,000") is Interval.YEAR
        assert detect_interval(None) is Interval.YEAR
        assert detect_interval("") is Interval.YEAR

    def test_an_hourly_rate_wins_over_an_annual_word_elsewhere(self):
        # Hourly ads nearly always also say "annually" about something else.
        assert detect_interval("Reviewed annually. Rate: $80 per hour.") is Interval.HOUR

    def test_the_caller_can_choose_a_different_default(self):
        assert detect_interval("$150,000", default=Interval.MONTH) is Interval.MONTH


class TestToAnnual:
    def test_each_period_scales_by_its_declared_multiplier(self):
        assert to_annual(100, Interval.HOUR) == 100 * 2080
        assert to_annual(100, Interval.DAY) == 100 * DAYS_PER_YEAR
        assert to_annual(100, Interval.WEEK) == 100 * 52
        assert to_annual(100, Interval.MONTH) == 100 * 12
        assert to_annual(100, Interval.YEAR) == 100

    def test_a_free_text_interval_is_accepted(self):
        # Boards send prose here; dropping a posting over a word is worse than
        # reading "per year" out of it.
        assert to_annual(100, "monthly") == 1200
        assert to_annual(100, "per hour") == 100 * 2080

    def test_an_unrecognised_interval_is_treated_as_yearly(self):
        assert to_annual(100, "per fortnight") == 100
        assert to_annual(100, None) == 100

    def test_nothing_in_nothing_out(self):
        assert to_annual(None, Interval.HOUR) is None

    def test_the_working_year_assumptions_agree_with_each_other(self):
        # 2080 hours is 40 across 52 weeks; 260 days is the same year stated
        # daily. If one moves without the other, a daily rate and an hourly rate
        # for the same job stop matching.
        assert MULTIPLIER[Interval.HOUR] == 8 * DAYS_PER_YEAR
        assert DAYS_PER_YEAR == 5 * MULTIPLIER[Interval.WEEK]

    def test_every_interval_has_a_multiplier(self):
        assert set(MULTIPLIER) == set(Interval)
