"""The constants get the same treatment as the data: they are only correct in
relation to each other, and none of them fails loudly on its own."""

from __future__ import annotations

from etl import config
from etl.guards import check_config
from etl.guards.config import MIN_TEXT_TRIM
from etl.money import Interval, to_annual


def test_the_shipped_configuration_is_consistent():
    verdict = check_config()
    assert verdict.ok, verdict.describe()
    assert verdict.warnings == [], verdict.describe()


class TestWhatItChecks:
    def test_the_salary_bounds_are_the_right_way_round(self):
        assert config.SALARY_MIN_USD < config.SALARY_MAX_USD

    def test_the_daily_budget_is_a_whole_number_of_batches(self):
        # A short last batch wastes the tail of the budget that is the binding
        # constraint on coverage.
        assert config.LLM_DAILY_JOB_LIMIT % config.LLM_BATCH_SIZE == 0

    def test_the_text_trim_reaches_the_requirements_section(self):
        # It was 1500 once, and the labels were unusable.
        assert config.LLM_TEXT_TRIM >= MIN_TEXT_TRIM

    def test_the_working_year_assumptions_describe_one_year(self):
        # Otherwise a daily rate and an hourly rate for the same job disagree.
        assert config.HOURS_PER_YEAR == 40 * config.WEEKS_PER_YEAR
        assert to_annual(1, Interval.WEEK) * 5 == to_annual(1, Interval.DAY)

    def test_the_fx_window_is_at_least_a_day(self):
        assert config.FX_MAX_AGE_DAYS >= 1

    def test_the_breaker_does_not_trip_on_one_failure(self):
        assert config.FETCH_CIRCUIT_BREAK >= 2

    def test_the_crawl_is_polite_and_bounded(self):
        assert config.FETCH_PAUSE_SEC >= 0
        assert config.HTTP_TIMEOUT > 0


def test_the_check_reports_rather_than_raises():
    # It runs before a crawl, where a stack trace is less useful than a list.
    verdict = check_config()
    assert hasattr(verdict, "findings")
    assert verdict.describe()
