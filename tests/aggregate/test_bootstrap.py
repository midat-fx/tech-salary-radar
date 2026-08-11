"""The interval that says how much to trust a premium."""

from __future__ import annotations

import pytest

from etl.aggregate import MIN_STRATUM, bootstrap_interval, weighted_premium
from etl.rng import SeededRng, bootstrap_rng


def stratum(with_values, without_values):
    return (list(with_values), list(without_values))


class TestWeightedPremium:
    def test_a_clean_twenty_percent_gap(self):
        pools = [stratum([120.0] * 10, [100.0] * 10)]
        assert weighted_premium(pools) == pytest.approx(20.0)

    def test_strata_are_weighted_by_their_with_pool(self):
        # A stratum where forty postings ask for a skill says more about it than
        # one where nine do.
        pools = [stratum([200.0] * 40, [100.0] * 10), stratum([100.0] * 2, [100.0] * 10)]
        assert weighted_premium(pools) > 90

    def test_a_stratum_missing_a_side_contributes_nothing(self):
        pools = [stratum([120.0] * 10, []), stratum([110.0] * 10, [100.0] * 10)]
        assert weighted_premium(pools) == pytest.approx(10.0)

    def test_no_usable_stratum_is_none_not_zero(self):
        # Zero would mean "measured, no premium"; None means "not measured".
        assert weighted_premium([]) is None
        assert weighted_premium([stratum([1.0], [])]) is None

    def test_a_zero_median_without_pool_is_skipped_rather_than_dividing(self):
        assert weighted_premium([stratum([100.0] * 5, [0.0] * 5)]) is None


class TestInterval:
    def test_it_brackets_the_point_estimate(self):
        pools = [stratum([120.0 + i for i in range(20)], [100.0 + i for i in range(20)])]
        point = weighted_premium(pools)
        low, high = bootstrap_interval(pools, bootstrap_rng(), replicates=200)
        assert low <= point <= high

    def test_the_same_seed_gives_the_same_interval(self):
        # An interval that moved between two aggregations of the same parquet
        # would be indistinguishable from the data having changed.
        pools = [stratum([120.0 + i for i in range(20)], [100.0 + i for i in range(20)])]
        first = bootstrap_interval(pools, SeededRng(1), replicates=100)
        second = bootstrap_interval(pools, SeededRng(1), replicates=100)
        assert first == second

    def test_a_wider_sample_gives_a_wider_interval(self):
        tight = [stratum([120.0] * 30, [100.0] * 30)]
        loose = [stratum([50.0 + i * 10 for i in range(30)], [100.0] * 30)]
        tight_lo, tight_hi = bootstrap_interval(tight, SeededRng(2), replicates=200)
        loose_lo, loose_hi = bootstrap_interval(loose, SeededRng(2), replicates=200)
        assert (loose_hi - loose_lo) > (tight_hi - tight_lo)

    def test_nothing_to_resample_yields_no_interval(self):
        # Reporting an interval built from the surviving replicates would
        # quietly describe a different, luckier population.
        assert bootstrap_interval([], SeededRng(3), replicates=100) == (None, None)

    def test_the_minimum_stratum_is_stated_not_implied(self):
        assert MIN_STRATUM == 8
