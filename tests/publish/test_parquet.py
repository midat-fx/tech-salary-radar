"""Writing a day so the commit that follows means something."""

from __future__ import annotations

import pytest

from etl.publish import partition_path, read_partition, write_partition
from etl.schema import InvariantViolated

DAY = "2026-08-19"


def snapshot(uid, **over):
    row = {
        "job_uid": uid,
        "snapshot_date": DAY,
        "source": "ashby",
        "company": "acme",
        "region": "us",
        "is_remote": False,
        "seniority": "senior",
        "is_management": False,
        "salary_min_usd": None,
        "salary_max_usd": None,
        "salary_mid_usd": None,
        "has_salary": False,
        "employment_type": None,
        "published_at": None,
    }
    row.update(over)
    return row


class TestWrite:
    def test_it_writes_where_the_partition_path_says(self, tmp_path):
        out = write_partition([snapshot("ashby:acme:1")], tmp_path, "snapshots", DAY)
        assert out == partition_path(tmp_path, "snapshots", DAY)
        assert out.exists()

    def test_rows_come_back_as_they_went_in(self, tmp_path):
        write_partition([snapshot("ashby:acme:1")], tmp_path, "snapshots", DAY)
        assert read_partition(tmp_path, "snapshots", DAY)[0]["job_uid"] == "ashby:acme:1"

    def test_an_unchanged_day_produces_an_identical_file(self, tmp_path):
        # Without this every run commits a new binary and the daily commit stops
        # being evidence that anything happened.
        rows = [snapshot(f"ashby:acme:{i}") for i in range(20)]
        write_partition(rows, tmp_path, "snapshots", DAY)
        first = partition_path(tmp_path, "snapshots", DAY).read_bytes()
        write_partition(list(reversed(rows)), tmp_path, "snapshots", DAY)
        assert partition_path(tmp_path, "snapshots", DAY).read_bytes() == first

    def test_a_day_is_replaced_not_appended(self, tmp_path):
        write_partition([snapshot("ashby:acme:1")], tmp_path, "snapshots", DAY)
        write_partition([snapshot("ashby:acme:2")], tmp_path, "snapshots", DAY)
        stored = {r["job_uid"] for r in read_partition(tmp_path, "snapshots", DAY)}
        assert stored == {"ashby:acme:2"}

    def test_the_skills_table_may_append_within_a_day(self, tmp_path):
        # A second run legitimately labels what the budget did not reach.
        label = lambda uid: {  # noqa: E731
            "job_uid": uid, "skill": "Python", "source": "llm",
            "prompt_version": "v1", "extracted_at": "2026-08-19T00:00:00Z",
        }
        write_partition([label("ashby:acme:1")], tmp_path, "skills", DAY)
        write_partition([label("ashby:acme:2")], tmp_path, "skills", DAY, append=True)
        assert len(read_partition(tmp_path, "skills", DAY)) == 2


class TestEmpty:
    def test_nothing_to_write_writes_nothing(self, tmp_path):
        assert write_partition([], tmp_path, "snapshots", DAY) is None
        assert not partition_path(tmp_path, "snapshots", DAY).exists()

    def test_an_emptied_day_removes_its_stale_file(self, tmp_path):
        # Leaving yesterday's rows under today's partition name is worse than
        # having no file at all.
        write_partition([snapshot("ashby:acme:1")], tmp_path, "snapshots", DAY)
        assert write_partition([], tmp_path, "snapshots", DAY) is None
        assert not partition_path(tmp_path, "snapshots", DAY).exists()

    def test_reading_a_missing_partition_is_an_empty_list(self, tmp_path):
        assert read_partition(tmp_path, "snapshots", "2026-01-01") == []


class TestValidation:
    def test_an_unstorable_row_is_dropped_and_logged(self, tmp_path):
        said = []
        write_partition(
            [snapshot("ashby:acme:1"), snapshot("not-a-uid")],
            tmp_path,
            "snapshots",
            DAY,
            log=said.append,
        )
        assert len(read_partition(tmp_path, "snapshots", DAY)) == 1
        assert "dropped 1" in said[0]

    def test_a_duplicate_key_still_raises(self, tmp_path):
        # That means the pipeline built the day wrong, not that a board sent
        # something odd.
        with pytest.raises(InvariantViolated, match="duplicate key"):
            write_partition(
                [snapshot("ashby:acme:1"), snapshot("ashby:acme:1")], tmp_path, "snapshots", DAY
            )

    def test_a_day_of_nothing_but_bad_rows_writes_no_file(self, tmp_path):
        assert write_partition([snapshot("bad")], tmp_path, "snapshots", DAY) is None
