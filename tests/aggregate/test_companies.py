"""Per-company pay: two different minimums, and why conflating them misleads."""

from __future__ import annotations

from etl.aggregate import company_stats, top_companies
from etl.aggregate.companies import MIN_SALARIES_FOR_MEDIAN, median_of
from etl.testing import JobSpec, build_dataset

DAY = "2026-08-19"


def dataset(tmp_path, jobs):
    return build_dataset(tmp_path, {DAY: jobs})


class TestMedianRule:
    def test_a_company_with_enough_salaries_gets_a_median(self, tmp_path):
        jobs = [
            JobSpec(f"ashby:acme:{i}", salary=200_000.0) for i in range(MIN_SALARIES_FOR_MEDIAN)
        ]
        stats = company_stats(dataset(tmp_path, jobs), DAY)[0]
        assert stats.has_median
        assert stats.median_usd == 200_000

    def test_a_company_below_the_threshold_is_listed_without_one(self, tmp_path):
        # Forty postings and three salaries must not produce a headline figure
        # resting on three people.
        jobs = [JobSpec(f"ashby:acme:{i}", salary=200_000.0) for i in range(2)] + [
            JobSpec(f"ashby:acme:x{i}", salary=None) for i in range(38)
        ]
        stats = company_stats(dataset(tmp_path, jobs), DAY)[0]
        assert stats.n == 40
        assert not stats.has_median
        assert stats.median_usd is None

    def test_management_pay_is_not_in_a_company_median(self, tmp_path):
        jobs = [
            JobSpec(f"ashby:acme:{i}", salary=100_000.0) for i in range(MIN_SALARIES_FOR_MEDIAN)
        ] + [JobSpec("ashby:acme:boss", salary=900_000.0, management=True)]
        stats = company_stats(dataset(tmp_path, jobs), DAY)[0]
        assert stats.median_usd == 100_000

    def test_the_helper_applies_the_same_rule(self):
        assert median_of([100.0, 200.0]) is None
        assert median_of([100.0] * MIN_SALARIES_FOR_MEDIAN) == 100
        assert median_of([]) is None


class TestShares:
    def test_it_reports_how_much_of_a_company_states_pay(self, tmp_path):
        jobs = [JobSpec(f"ashby:acme:{i}", salary=200_000.0) for i in range(5)] + [
            JobSpec(f"ashby:acme:x{i}", salary=None) for i in range(5)
        ]
        stats = company_stats(dataset(tmp_path, jobs), DAY)[0]
        assert stats.salary_share == 0.5

    def test_it_reports_the_remote_share(self, tmp_path):
        jobs = [JobSpec("ashby:acme:1", salary=None, remote=True), JobSpec("ashby:acme:2")]
        assert company_stats(dataset(tmp_path, jobs), DAY)[0].remote_share == 0.5


class TestOrdering:
    def test_the_biggest_employer_comes_first(self, tmp_path):
        jobs = [JobSpec(f"ashby:big:{i}", company="big") for i in range(5)] + [
            JobSpec("ashby:small:1", company="small")
        ]
        assert [s.company for s in company_stats(dataset(tmp_path, jobs), DAY)] == ["big", "small"]

    def test_ties_break_by_name_so_two_runs_agree(self, tmp_path):
        jobs = [JobSpec("ashby:zeta:1", company="zeta"), JobSpec("ashby:alpha:1", company="alpha")]
        assert [s.company for s in company_stats(dataset(tmp_path, jobs), DAY)] == ["alpha", "zeta"]

    def test_the_published_shape_carries_a_board_url(self, tmp_path):
        rows = top_companies(dataset(tmp_path, [JobSpec("ashby:acme:1")]), DAY)
        assert rows[0]["url"].endswith("/acme")
        assert set(rows[0]) == {"company", "n", "url", "median_usd", "n_paid", "remote_share"}

    def test_the_limit_cuts_the_tail(self, tmp_path):
        jobs = [JobSpec(f"ashby:c{i}:1", company=f"c{i}") for i in range(15)]
        assert len(top_companies(dataset(tmp_path, jobs), DAY, limit=3)) == 3
