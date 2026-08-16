"""Reading a day written by older code — the promise, actually applied."""

from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from etl.schema import JOBS, SKILLS, SchemaVersion, detect_version, read_partition_versioned
from etl.schema.migrations import MARKER_COLUMN, compatibility_of
from etl.schema.version import Compatibility


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


def skill_row(uid="ashby:acme:1", **over):
    row = {"job_uid": uid, "skill": "Python", "extracted_at": "2026-08-19T00:00:00Z"}
    row.update(over)
    return row


class TestDetect:
    def test_a_stamped_partition_reports_its_version(self):
        assert detect_version([{MARKER_COLUMN: "1.3"}]) == SchemaVersion(1, 3)

    def test_an_unstamped_partition_has_none(self):
        assert detect_version([{"job_uid": "x"}]) is None

    def test_a_mixed_partition_is_read_as_its_oldest_half(self):
        # A same-day append across a deploy. Reading it as the newer version
        # leaves a column unfilled for the older half.
        rows = [{MARKER_COLUMN: "1.3"}, {MARKER_COLUMN: "1.1"}]
        assert detect_version(rows) == SchemaVersion(1, 1)

    def test_an_unparseable_marker_is_ignored_not_trusted(self):
        assert detect_version([{MARKER_COLUMN: "yesterday"}]) is None


class TestRead:
    def test_an_old_partition_is_filled_and_the_fill_is_reported(self, tmp_path):
        # The whole point: a silent fill turns "this day could not have known"
        # into "this day says no".
        path = write(tmp_path / "skills" / "dt=2026-07-18" / "part.parquet", [skill_row()])
        result = read_partition_versioned(SKILLS, path)
        assert result.needed_fill
        assert set(result.filled) == {"source", "prompt_version"}
        assert result.rows[0]["prompt_version"] == "v1"
        assert "filled" in result.describe()

    def test_a_current_partition_needs_nothing(self, tmp_path):
        row = skill_row(source="llm", prompt_version="v1")
        row[MARKER_COLUMN] = "1.3"
        path = write(tmp_path / "skills" / "dt=2026-08-19" / "part.parquet", [row])
        result = read_partition_versioned(SKILLS, path)
        assert not result.needed_fill
        assert result.written_with == SchemaVersion(1, 3)

    def test_the_marker_column_never_reaches_the_caller(self, tmp_path):
        row = skill_row(source="llm", prompt_version="v1")
        row[MARKER_COLUMN] = "1.3"
        path = write(tmp_path / "p" / "part.parquet", [row])
        assert MARKER_COLUMN not in read_partition_versioned(SKILLS, path).rows[0]

    def test_a_missing_partition_is_empty_rather_than_an_error(self, tmp_path):
        result = read_partition_versioned(JOBS, tmp_path / "nope" / "part.parquet")
        assert result.rows == []
        assert result.note == "no such partition"

    def test_an_incompatible_major_refuses_to_be_read(self, tmp_path):
        from etl.schema import InvariantViolated

        row = skill_row()
        row[MARKER_COLUMN] = "2.0"
        path = write(tmp_path / "p" / "part.parquet", [row])
        with pytest.raises(InvariantViolated, match="different major"):
            read_partition_versioned(SKILLS, path)


class TestPeek:
    def test_compatibility_can_be_read_without_the_whole_file(self, tmp_path):
        row = skill_row()
        row[MARKER_COLUMN] = "1.0"
        path = write(tmp_path / "p" / "part.parquet", [row])
        assert compatibility_of(path) == Compatibility.OLDER_FILL_DEFAULTS

    def test_an_absent_file_says_absent(self, tmp_path):
        assert compatibility_of(tmp_path / "nope.parquet") == "absent"
