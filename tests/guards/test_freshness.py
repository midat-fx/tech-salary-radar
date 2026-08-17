"""Whether the day's inputs were current — a question the row count cannot answer."""

from __future__ import annotations

from etl.guards import check_freshness
from etl.testing import FixedClock

NOW = FixedClock().now()
DAY = "2026-08-19"


def row(**over):
    base = {"snapshot_date": DAY, "published_at": "2026-08-18T00:00:00Z"}
    base.update(over)
    return base


class TestFxAge:
    def test_a_current_rate_table_is_clear(self):
        assert check_freshness([row()], DAY, "2026-08-19", NOW).findings == []

    def test_an_old_rate_table_is_a_warning(self):
        # Every converted figure in the day rests on it.
        verdict = check_freshness([row()], DAY, "2026-08-01", NOW)
        assert verdict.ok
        assert "rate table is" in verdict.describe()

    def test_an_undated_rate_table_is_a_warning(self):
        assert "no date" in check_freshness([row()], DAY, None, NOW).describe()


class TestPartitionDate:
    def test_a_row_dated_differently_from_its_partition_is_refused(self):
        # The run's idea of today moved mid-flight, which is exactly what the
        # context exists to prevent.
        verdict = check_freshness([row(snapshot_date="2026-08-18")], DAY, "2026-08-19", NOW)
        assert not verdict.ok
        assert "2026-08-18" in verdict.describe()

    def test_a_consistent_day_passes(self):
        assert check_freshness([row(), row()], DAY, "2026-08-19", NOW).ok


class TestStaleCrawl:
    def test_a_crawl_whose_newest_posting_is_ancient_is_flagged(self):
        # None of this changes the row count, which is why the other guards miss it.
        verdict = check_freshness([row(published_at="2026-06-01T00:00:00Z")], DAY, "2026-08-19", NOW)
        assert verdict.ok
        assert "serving a cache" in verdict.describe()

    def test_a_quiet_fortnight_is_not_flagged(self):
        # Hiring genuinely stops over the winter holidays.
        assert check_freshness([row(published_at="2026-08-10T00:00:00Z")], DAY, "2026-08-19", NOW).findings == []

    def test_postings_with_no_date_are_simply_not_evidence(self):
        assert check_freshness([row(published_at=None)], DAY, "2026-08-19", NOW).findings == []


def test_an_empty_day_is_left_to_the_other_guards():
    assert check_freshness([], DAY, None, NOW).findings == []
