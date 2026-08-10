"""What stops a day from being written, and what merely gets said out loud."""

from __future__ import annotations

from etl.guards import CircuitBreaker, Severity, Verdict, check_plausibility, check_volume
from etl.guards.volume import SOURCE_FLOOR, TOTAL_FLOOR
from etl.testing import JobSpec, build_dataset


def snap(uid, **over):
    base = {
        "job_uid": uid,
        "source": "ashby",
        "region": "us",
        "seniority": "senior",
        "has_salary": True,
    }
    base.update(over)
    return base


class TestVerdict:
    def test_a_refusal_stops_the_day_and_a_warning_does_not(self):
        verdict = Verdict().add("g", Severity.WARN, "odd").add("g", Severity.REFUSE, "no")
        assert not verdict.ok
        assert len(verdict.warnings) == 1 and len(verdict.refusals) == 1

    def test_warnings_alone_still_pass(self):
        assert Verdict().add("g", Severity.WARN, "odd").ok

    def test_findings_are_reported_together_not_one_at_a_time(self):
        # A guard that raised would hide the others behind whichever ran first.
        verdict = Verdict().add("a", Severity.REFUSE, "one").add("b", Severity.REFUSE, "two")
        assert "one" in verdict.describe() and "two" in verdict.describe()

    def test_nothing_found_says_so(self):
        assert Verdict().describe() == "guards: clear"


class TestVolume:
    def build(self, tmp_path, days):
        return build_dataset(tmp_path, days)

    def test_no_history_means_no_opinion(self, tmp_path):
        # The launch week must not be blocked by a guard with nothing to compare.
        assert check_volume(tmp_path, "2026-08-19", {"ashby": 1}).ok

    def test_a_normal_day_passes(self, tmp_path):
        days = {
            f"2026-08-1{i}": [JobSpec(f"ashby:acme:{i}{n}", salary=100_000.0) for n in range(10)]
            for i in range(1, 5)
        }
        self.build(tmp_path, days)
        assert check_volume(tmp_path, "2026-08-19", {"ashby": 10}).ok

    def test_a_source_collapse_is_refused(self, tmp_path):
        days = {
            f"2026-08-1{i}": [JobSpec(f"ashby:acme:{i}{n}", salary=100_000.0) for n in range(10)]
            for i in range(1, 5)
        }
        self.build(tmp_path, days)
        verdict = check_volume(tmp_path, "2026-08-19", {"ashby": int(10 * SOURCE_FLOOR) - 1})
        assert not verdict.ok
        assert "ashby" in verdict.describe()

    def test_the_total_floor_catches_what_the_source_floor_cannot(self, tmp_path):
        # Every source down by the same amount, each individually inside its own
        # floor, and the day as a whole below the expected total.
        per_source = 20
        days = {}
        for i in range(1, 5):
            days[f"2026-08-1{i}"] = [
                JobSpec(f"ashby:acme:{i}-{n}", salary=100_000.0, source="ashby")
                for n in range(per_source)
            ] + [
                JobSpec(f"lever:acme:{i}-{n}", salary=100_000.0, source="lever")
                for n in range(per_source)
            ]
        self.build(tmp_path, days)
        today = int(per_source * SOURCE_FLOOR) + 1        # above every source floor
        assert 2 * today < TOTAL_FLOOR * 2 * per_source   # ...and below the total one
        verdict = check_volume(tmp_path, "2026-08-19", {"ashby": today, "lever": today})
        assert not verdict.ok
        assert "total" in verdict.describe()
        assert verdict.refusals[0].guard == "volume"

    def test_a_new_source_is_a_warning_not_a_refusal(self, tmp_path):
        days = {
            f"2026-08-1{i}": [JobSpec(f"ashby:acme:{i}{n}", salary=100_000.0) for n in range(10)]
            for i in range(1, 5)
        }
        self.build(tmp_path, days)
        verdict = check_volume(tmp_path, "2026-08-19", {"ashby": 10, "greenhouse": 5})
        assert verdict.ok
        assert "greenhouse" in verdict.describe()


class TestPlausibility:
    def test_an_ordinary_day_is_clear(self):
        rows = [snap(f"ashby:acme:{i}", region="us" if i % 2 else "eu") for i in range(20)]
        assert check_plausibility(rows).ok
        assert check_plausibility(rows).warnings == []

    def test_an_empty_day_is_refused(self):
        assert not check_plausibility([]).ok

    def test_salaries_vanishing_is_a_warning(self):
        # The parser is more likely broken than the market suddenly private —
        # but it is a strong signal and a weak proof, so the day still lands.
        rows = [snap(f"ashby:acme:{i}", has_salary=False) for i in range(50)]
        verdict = check_plausibility(rows)
        assert verdict.ok
        assert "carry a salary" in verdict.describe()

    def test_regions_collapsing_is_a_warning(self):
        rows = [snap(f"ashby:acme:{i}", region="other") for i in range(50)]
        assert "recognised region" in check_plausibility(rows).describe()

    def test_levels_collapsing_is_a_warning(self):
        rows = [snap(f"ashby:acme:{i}", seniority="unspecified") for i in range(50)]
        assert "unspecified" in check_plausibility(rows).describe()

    def test_a_single_source_day_is_flagged_once_it_is_large(self):
        rows = [snap(f"ashby:acme:{i}") for i in range(200)]
        assert "contributed nothing" in check_plausibility(rows).describe()

    def test_a_small_single_source_day_is_not_flagged(self):
        # The launch week and any short run are legitimately one board.
        rows = [snap(f"ashby:acme:{i}") for i in range(5)]
        assert "contributed nothing" not in check_plausibility(rows).describe()


class TestBreaker:
    def test_one_bad_board_does_not_stop_a_source(self):
        breaker = CircuitBreaker(threshold=3)
        assert not breaker.record_failure("greenhouse")
        assert not breaker.is_open("greenhouse")

    def test_consecutive_failures_trip_it(self):
        breaker = CircuitBreaker(threshold=3)
        breaker.record_failure("greenhouse")
        breaker.record_failure("greenhouse")
        assert breaker.record_failure("greenhouse")
        assert breaker.is_open("greenhouse")

    def test_a_success_resets_the_run(self):
        # Consecutive, not total: a source that fails a board here and there is
        # working, and that is what tells the two cases apart.
        breaker = CircuitBreaker(threshold=3)
        breaker.record_failure("greenhouse")
        breaker.record_failure("greenhouse")
        breaker.record_success("greenhouse")
        breaker.record_failure("greenhouse")
        assert not breaker.is_open("greenhouse")

    def test_sources_are_independent(self):
        breaker = CircuitBreaker(threshold=1)
        breaker.record_failure("greenhouse")
        assert breaker.is_open("greenhouse")
        assert not breaker.is_open("ashby")

    def test_it_trips_once_and_reports_which_sources(self):
        breaker = CircuitBreaker(threshold=1)
        assert breaker.record_failure("lever")
        assert not breaker.record_failure("lever")
        assert breaker.tripped_sources == ("lever",)

    def test_the_description_carries_both_counts(self):
        breaker = CircuitBreaker(threshold=5)
        breaker.record_success("ashby")
        breaker.record_failure("ashby")
        assert "1 ok / 1 failed" in breaker.describe()

    def test_nothing_attempted_says_so(self):
        assert "no boards attempted" in CircuitBreaker().describe()
