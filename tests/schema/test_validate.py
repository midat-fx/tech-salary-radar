"""What a row must satisfy before it is stored, and how an old day is read."""

from __future__ import annotations

import pytest

from etl.schema import (
    JOBS,
    SKILLS,
    SNAPSHOTS,
    InvariantViolated,
    MissingColumn,
    SchemaVersion,
    UnknownColumn,
    WrongType,
    coerce_row,
    fill_missing,
    validate_row,
    validate_rows,
)


def snapshot_row(**over):
    row = {
        "job_uid": "greenhouse:acme:1",
        "snapshot_date": "2026-08-19",
        "source": "greenhouse",
        "company": "acme",
        "region": "us",
        "is_remote": False,
        "seniority": "senior",
        "is_management": False,
        "salary_min_usd": 150000.0,
        "salary_max_usd": 190000.0,
        "salary_mid_usd": 170000.0,
        "has_salary": True,
        "employment_type": None,
        "published_at": "2026-08-01T00:00:00Z",
    }
    row.update(over)
    return row


class TestColumns:
    def test_a_complete_row_passes(self):
        assert validate_row(SNAPSHOTS, snapshot_row())["job_uid"] == "greenhouse:acme:1"

    def test_an_unknown_column_is_refused_not_dropped(self):
        # Every one of these seen so far was a half-finished rename; dropping it
        # produced a column that was quietly always null.
        with pytest.raises(UnknownColumn, match="salary_currency"):
            validate_row(SNAPSHOTS, snapshot_row(salary_currency="USD"))

    def test_a_missing_column_is_refused(self):
        row = snapshot_row()
        del row["region"]
        with pytest.raises(MissingColumn, match="region"):
            validate_row(SNAPSHOTS, row)

    def test_a_null_in_a_non_nullable_column_is_a_missing_column(self):
        with pytest.raises(MissingColumn, match="company"):
            validate_row(SNAPSHOTS, snapshot_row(company=None))

    def test_a_null_in_a_nullable_column_is_fine(self):
        # No posted salary is a fact about the job, not a gap to fill with zero.
        row = validate_row(
            SNAPSHOTS,
            snapshot_row(
                salary_min_usd=None, salary_max_usd=None, salary_mid_usd=None, has_salary=False
            ),
        )
        assert row["salary_mid_usd"] is None


class TestTypes:
    def test_a_string_in_a_numeric_column_is_refused(self):
        with pytest.raises(WrongType, match="salary_mid_usd"):
            validate_row(SNAPSHOTS, snapshot_row(salary_mid_usd="170000"))

    def test_a_bool_does_not_pass_as_a_number(self):
        # True is an int in Python; a boolean reaching a salary column is a real
        # mistake and would store as 1.0.
        with pytest.raises(WrongType):
            validate_row(SNAPSHOTS, snapshot_row(salary_mid_usd=True))

    def test_an_int_is_widened_to_float_rather_than_refused(self):
        # An Ashby range of exactly 180000 arrives as an int; a converted EUR
        # figure never does, and parquet cannot hold both in one column.
        row = validate_row(SNAPSHOTS, snapshot_row(salary_mid_usd=170000))
        assert isinstance(row["salary_mid_usd"], float)

    def test_coerce_leaves_everything_else_alone(self):
        row = snapshot_row()
        assert coerce_row(SNAPSHOTS, row)["company"] == row["company"]


class TestInvariants:
    def test_an_inverted_salary_range_is_refused(self):
        with pytest.raises(InvariantViolated, match="above"):
            validate_row(SNAPSHOTS, snapshot_row(salary_min_usd=200000.0, salary_max_usd=100000.0))

    def test_has_salary_without_a_figure_is_refused(self):
        with pytest.raises(InvariantViolated, match="has_salary"):
            validate_row(SNAPSHOTS, snapshot_row(salary_mid_usd=None))

    def test_a_figure_without_has_salary_is_refused(self):
        # The dashboard filters on has_salary and medians on the figure; the two
        # disagreeing is how a number gets published that no filter explains.
        with pytest.raises(InvariantViolated, match="has_salary is false"):
            validate_row(SNAPSHOTS, snapshot_row(has_salary=False))

    def test_a_region_outside_the_bucket_set_is_refused(self):
        with pytest.raises(InvariantViolated, match="region"):
            validate_row(SNAPSHOTS, snapshot_row(region="apac"))

    def test_a_malformed_uid_is_refused(self):
        with pytest.raises(InvariantViolated, match="job_uid"):
            validate_row(SNAPSHOTS, snapshot_row(job_uid="acme-1"))

    def test_a_uid_whose_id_contains_a_colon_is_accepted(self):
        # Ashby ids do contain colons; the separator has to survive them.
        assert validate_row(SNAPSHOTS, snapshot_row(job_uid="ashby:acme:a:b:c"))


class TestPartitionLevel:
    def test_duplicate_keys_inside_one_partition_are_refused(self):
        rows = [snapshot_row(), snapshot_row()]
        with pytest.raises(InvariantViolated, match="duplicate key"):
            validate_rows(SNAPSHOTS, rows)

    def test_distinct_keys_pass(self):
        rows = [snapshot_row(), snapshot_row(job_uid="greenhouse:acme:2")]
        assert len(validate_rows(SNAPSHOTS, rows)) == 2

    def test_the_skills_table_is_keyed_by_job_and_skill_together(self):
        # One job legitimately has many skill rows; the same skill twice is a
        # double count in every premium that follows.
        base = {
            "job_uid": "lever:acme:9",
            "skill": "Python",
            "source": "llm",
            "prompt_version": "v1",
            "extracted_at": "2026-08-19T07:48:11Z",
        }
        assert len(validate_rows(SKILLS, [base, {**base, "skill": "SQL"}])) == 2
        with pytest.raises(InvariantViolated, match="duplicate key"):
            validate_rows(SKILLS, [base, dict(base)])

    def test_a_processed_job_with_no_skills_stores_one_null_row(self):
        # This is how "labelled, found nothing" is told apart from "never
        # labelled" — the distinction ADR 0003 turns into a statistical rule.
        row = {
            "job_uid": "lever:acme:9",
            "skill": None,
            "source": "llm",
            "prompt_version": "v1",
            "extracted_at": "2026-08-19T07:48:11Z",
        }
        assert validate_row(SKILLS, row)["skill"] is None


class TestFillMissing:
    def test_columns_added_since_are_filled_and_reported(self):
        old = [{name: None for name in JOBS.names if name != "currency_original"}]
        old[0].update(
            {
                "job_uid": "lever:acme:1",
                "first_seen": "2026-07-18",
                "source": "lever",
                "company": "acme",
            }
        )
        rows, filled = fill_missing(JOBS, old, SchemaVersion(1, 0))
        assert filled == ["currency_original"]
        assert rows[0]["currency_original"] is None

    def test_nothing_is_filled_for_a_current_partition(self):
        rows, filled = fill_missing(SNAPSHOTS, [snapshot_row()], SchemaVersion(1, 3))
        assert filled == []
        assert rows[0] == snapshot_row()

    def test_a_default_is_a_value_not_always_null(self):
        old = [{"job_uid": "lever:acme:1", "skill": "Go", "extracted_at": "2026-07-18T00:00:00Z"}]
        rows, filled = fill_missing(SKILLS, old, SchemaVersion(1, 1))
        assert set(filled) == {"source", "prompt_version"}
        # An unmarked label came from the only prompt that existed then.
        assert rows[0]["prompt_version"] == "v1"
        assert rows[0]["source"] == "llm"

    def test_an_incompatible_major_is_refused_rather_than_filled(self):
        with pytest.raises(InvariantViolated, match="different major"):
            fill_missing(SNAPSHOTS, [snapshot_row()], SchemaVersion(2, 0))

    def test_an_empty_partition_reports_every_column_as_filled(self):
        rows, filled = fill_missing(SNAPSHOTS, [], SchemaVersion(1, 0))
        assert rows == []
        assert filled == sorted(SNAPSHOTS.names)
