"""A week of runs, so the comparative questions can be asked at all."""

from __future__ import annotations

from etl.report import JOURNAL_FIELDS, append_run, journal_line, read_journal


def values(**over):
    base = {
        "raw_jobs": 16_500,
        "snapshot_rows": 6_546,
        "new_rows": 412,
        "with_salary": 1_431,
        "salary_share": 0.2186,
        "duplicates_removed": 54,
        "skill_rows": 700,
        "llm_missing_ids": 3,
        "guard_verdict": "clear",
    }
    base.update(over)
    return base


class TestLine:
    def test_it_is_the_day_then_the_tracked_fields_in_order(self):
        cells = journal_line("2026-08-19", values()).split("\t")
        assert cells[0] == "2026-08-19"
        assert len(cells) == len(JOURNAL_FIELDS) + 1
        assert cells[1] == "16500"

    def test_a_share_is_formatted_the_same_way_as_in_the_report(self):
        assert "21.9%" in journal_line("2026-08-19", values())

    def test_a_missing_number_is_a_dash_so_columns_stay_aligned(self):
        line = journal_line("2026-08-19", values(skill_rows=None))
        assert "\t-\t" in line


class TestAppend:
    def test_a_new_journal_gets_a_header(self, tmp_path):
        append_run(tmp_path, "2026-08-19", values())
        header = (tmp_path / "run_journal.tsv").read_text().splitlines()[0]
        assert header.startswith("day\t")
        assert "salary_share" in header

    def test_runs_accumulate(self, tmp_path):
        append_run(tmp_path, "2026-08-18", values())
        append_run(tmp_path, "2026-08-19", values(snapshot_rows=6_000))
        assert len(read_journal(tmp_path)) == 2

    def test_re_running_a_day_replaces_its_line(self, tmp_path):
        # Two lines for one day would make every later comparison count it twice.
        append_run(tmp_path, "2026-08-19", values(snapshot_rows=1))
        append_run(tmp_path, "2026-08-19", values(snapshot_rows=2))
        entries = read_journal(tmp_path)
        assert len(entries) == 1
        assert entries[0].get("snapshot_rows") == "2"

    def test_entries_come_back_in_day_order(self, tmp_path):
        append_run(tmp_path, "2026-08-19", values())
        append_run(tmp_path, "2026-08-17", values())
        assert [e.day for e in read_journal(tmp_path)] == ["2026-08-17", "2026-08-19"]

    def test_a_field_can_be_read_back_by_name(self, tmp_path):
        append_run(tmp_path, "2026-08-19", values(guard_verdict="refused"))
        assert read_journal(tmp_path)[0].get("guard_verdict") == "refused"
        assert read_journal(tmp_path)[0].get("not_a_field") is None

    def test_no_journal_yet_is_an_empty_list(self, tmp_path):
        assert read_journal(tmp_path) == []
