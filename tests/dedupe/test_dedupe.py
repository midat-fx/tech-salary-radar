"""One job on two boards: finding it, choosing a copy, and keeping what the
losing copy knew."""

from __future__ import annotations

from etl.dedupe import (
    deduplicate,
    fingerprint,
    merge_group,
    normalise_title,
    rank_of,
    sort_candidates,
)


def row(uid, source="ashby", title="Senior Backend Engineer", company="acme",
        location="Berlin, Germany", salary=None, **over):
    base = {
        "job_uid": uid,
        "source": source,
        "company": company,
        "title": title,
        "location_raw": location,
        "region": "eu",
        "seniority": "senior",
        "snapshot_date": "2026-08-19",
        "salary_min_usd": salary,
        "salary_max_usd": salary,
        "salary_mid_usd": salary,
        "has_salary": salary is not None,
        "employment_type": None,
        "published_at": None,
        "apply_url": None,
        "currency_original": None,
        "salary_min_orig": None,
        "salary_max_orig": None,
        "salary_interval_orig": None,
    }
    base.update(over)
    return base


class TestTitle:
    def test_decoration_is_stripped(self):
        assert normalise_title("Senior Backend Engineer (Remote)") == "senior backend engineer"
        assert normalise_title("Backend Engineer m/f/d") == "backend engineer"

    def test_level_words_are_kept(self):
        # Seniority rides in the fingerprint separately, but the title must not
        # lose it either: "Senior Engineer" is not "Engineer".
        assert normalise_title("Senior Engineer") != normalise_title("Engineer")

    def test_language_names_survive_the_punctuation_strip(self):
        # Collapsing C++ and C# to "c" would merge two different jobs, which is
        # the one error this must never make.
        assert normalise_title("C++ Engineer") != normalise_title("C# Engineer")
        assert "c++" in normalise_title("C++ Engineer")

    def test_nothing_in_nothing_out(self):
        assert normalise_title(None) == ""


class TestFingerprint:
    def test_the_same_job_on_two_boards_shares_a_key(self):
        a = fingerprint(row("greenhouse:acme:1", "greenhouse"))
        b = fingerprint(row("lever:acme:9", "lever"))
        assert a == b

    def test_two_different_roles_do_not(self):
        a = fingerprint(row("ashby:acme:1", title="Senior Backend Engineer"))
        b = fingerprint(row("ashby:acme:2", title="Senior Frontend Engineer"))
        assert a != b

    def test_the_same_title_at_two_companies_does_not(self):
        a = fingerprint(row("ashby:acme:1", company="acme"))
        b = fingerprint(row("ashby:other:1", company="other"))
        assert a != b

    def test_the_same_role_in_two_cities_does_not(self):
        a = fingerprint(row("ashby:acme:1", location="Berlin, Germany"))
        b = fingerprint(row("ashby:acme:2", location="Madrid, Spain"))
        assert a != b

    def test_two_spellings_of_one_place_do(self):
        a = fingerprint(row("ashby:acme:1", location="Zürich"))
        b = fingerprint(row("lever:acme:2", location="Zurich"))
        assert a == b

    def test_a_row_with_no_title_cannot_be_keyed(self):
        # Merging on an empty key would collapse every broken posting into one.
        assert not fingerprint(row("ashby:acme:1", title="")).is_usable
        assert not fingerprint(row("ashby:acme:1", company="")).is_usable


class TestPriority:
    def test_boards_rank_by_how_much_they_state_outright(self):
        assert rank_of("ashby") < rank_of("lever") < rank_of("greenhouse")

    def test_an_unknown_board_sorts_last_rather_than_raising(self):
        assert rank_of("workday") > rank_of("greenhouse")
        assert rank_of(None) > rank_of("greenhouse")

    def test_a_copy_with_a_salary_beats_a_better_board_without_one(self):
        # Going by board alone would prefer an empty Ashby posting over a
        # Greenhouse ad that states a range, which is backwards.
        rich = row("greenhouse:acme:1", "greenhouse", salary=180_000.0)
        poor = row("ashby:acme:1", "ashby")
        assert sort_candidates([poor, rich])[0]["job_uid"] == "greenhouse:acme:1"

    def test_the_tie_break_is_stable_across_runs(self):
        a, b = row("ashby:acme:1"), row("ashby:acme:2")
        assert sort_candidates([a, b]) == sort_candidates([b, a])


class TestMerge:
    def test_a_lone_posting_is_returned_unchanged(self):
        result = merge_group([row("ashby:acme:1")])
        assert not result.is_merged
        assert result.row["job_uid"] == "ashby:acme:1"

    def test_the_winner_keeps_its_own_identity(self):
        result = merge_group([row("greenhouse:acme:1", "greenhouse"), row("ashby:acme:9", "ashby")])
        assert result.row["job_uid"] == "ashby:acme:9"
        assert result.row["source"] == "ashby"
        assert result.duplicates == ("greenhouse:acme:1",)

    def test_the_copy_that_states_a_salary_wins_outright(self):
        # No filling needed: the priority rule already put the informative copy
        # first, which is the point of ranking salary above board.
        result = merge_group(
            [row("ashby:acme:9", "ashby"), row("greenhouse:acme:1", "greenhouse", salary=180_000.0)]
        )
        assert result.row["job_uid"] == "greenhouse:acme:1"
        assert result.row["salary_mid_usd"] == 180_000.0
        assert result.filled == ()

    def test_a_field_the_winner_lacks_is_filled_from_the_losing_copy(self):
        # Greenhouse never sends employment_type and often has no publish date;
        # the Lever copy of the same job has both, and throwing them away loses
        # real information about the market.
        winner = row("greenhouse:acme:1", "greenhouse", salary=180_000.0)
        loser = row("lever:acme:9", "lever", employment_type="FullTime",
                    published_at="2026-08-01T00:00:00Z")
        result = merge_group([winner, loser])
        assert result.row["job_uid"] == "greenhouse:acme:1"
        assert result.row["employment_type"] == "FullTime"
        assert result.row["published_at"] == "2026-08-01T00:00:00Z"
        assert set(result.filled) == {"employment_type", "published_at"}

    def test_an_absent_salary_is_filled_when_neither_copy_won_on_it(self):
        winner = row("ashby:acme:9", "ashby")
        loser = row("lever:acme:1", "lever")
        loser["salary_mid_usd"] = None
        result = merge_group([winner, loser])
        assert result.row["has_salary"] is False
        assert result.row["salary_mid_usd"] is None

    def test_a_stated_value_is_never_overwritten(self):
        # A disagreement between two boards is not something this layer can
        # resolve, and preferring one quietly would make the figure depend on
        # merge order.
        result = merge_group(
            [
                row("ashby:acme:9", "ashby", salary=200_000.0),
                row("lever:acme:1", "lever", salary=100_000.0),
            ]
        )
        assert result.row["salary_mid_usd"] == 200_000.0
        assert result.filled == ()

    def test_the_salary_flag_is_recomputed_not_copied(self):
        # Filling a figure without the flag stores a number the dashboard hides;
        # the flag without a figure fails the writer's invariant.
        result = merge_group([row("ashby:acme:9"), row("lever:acme:1", "lever", salary=150_000.0)])
        assert result.row["has_salary"] == (result.row["salary_mid_usd"] is not None)


class TestDeduplicate:
    def test_a_cross_board_duplicate_collapses_to_one_row(self):
        rows = [row("greenhouse:acme:1", "greenhouse"), row("lever:acme:9", "lever")]
        out, report = deduplicate(rows)
        assert len(out) == 1
        assert report.duplicates_removed == 1
        assert report.groups_merged == 1

    def test_distinct_jobs_survive(self):
        rows = [row("ashby:acme:1", title="Backend Engineer"), row("ashby:acme:2", title="SRE")]
        out, report = deduplicate(rows)
        assert len(out) == 2
        assert report.duplicates_removed == 0

    def test_unkeyable_rows_are_left_alone_and_counted(self):
        rows = [row("ashby:acme:1"), row("ashby:acme:2", title="")]
        out, report = deduplicate(rows)
        assert len(out) == 2
        assert report.unusable_keys == 1

    def test_the_output_order_is_stable(self):
        rows = [row(f"ashby:acme:{i}", title=f"Engineer {i}") for i in range(5)]
        assert [r["job_uid"] for r in deduplicate(rows)[0]] == [
            r["job_uid"] for r in deduplicate(list(reversed(rows)))[0]
        ]

    def test_the_report_says_what_it_did(self):
        rows = [row("greenhouse:acme:1", "greenhouse", salary=180_000.0), row("lever:acme:9", "lever")]
        _, report = deduplicate(rows)
        line = report.describe()
        assert "2 -> 1 rows" in line
        assert "1 cross-board duplicates" in line
        assert report.duplicate_share == 0.5

    def test_an_empty_day_does_not_divide_by_zero(self):
        out, report = deduplicate([])
        assert out == []
        assert report.duplicate_share == 0.0
