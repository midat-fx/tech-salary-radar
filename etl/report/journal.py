"""Keep each run's report, so a week of them can be compared.

The report is written to stdout and, in a cron job, into a log nobody keeps. A
single run's numbers are worth little on their own — the questions that matter
are comparative. Did coverage fall? Has the model been dropping more ids since
Tuesday? Was the day the guards refused preceded by anything visible?

One line per run, in a fixed field order, appended. Not JSON-per-line: this is
read by a person scrolling, and the same fixed order that makes the text
diffable makes a column of it scannable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from etl.report.fields import FIELD_ORDER
from etl.report.render import format_value

__all__ = ["JOURNAL_NAME", "JOURNAL_FIELDS", "journal_line", "append_run", "read_journal"]

JOURNAL_NAME = "run_journal.tsv"

#: The subset worth a column. The full report is too wide for one line, and
#: these are the numbers whose movement is the question.
JOURNAL_FIELDS = (
    "raw_jobs",
    "snapshot_rows",
    "new_rows",
    "with_salary",
    "salary_share",
    "duplicates_removed",
    "skill_rows",
    "llm_missing_ids",
    "guard_verdict",
)

_BY_KEY = {field.key: field for field in FIELD_ORDER}


def journal_line(day: str, values: dict) -> str:
    """One tab-separated row: the day, then the tracked fields in order."""
    cells = [day]
    for key in JOURNAL_FIELDS:
        field = _BY_KEY[key]
        cells.append(format_value(field, values.get(key)))
    return "\t".join(cells)


def _header() -> str:
    return "\t".join(("day", *JOURNAL_FIELDS))


@dataclass(frozen=True)
class JournalEntry:
    """One past run, as read back."""

    day: str
    cells: tuple[str, ...]

    def get(self, key: str) -> str | None:
        try:
            return self.cells[JOURNAL_FIELDS.index(key)]
        except ValueError:
            return None


def append_run(data_dir: str | Path, day: str, values: dict) -> Path:
    """Add this run to the journal, writing the header if the file is new.

    A day that already has a line is replaced rather than duplicated: re-running
    a day is normal, and two lines for it would make every later comparison
    count it twice.
    """
    path = Path(data_dir) / JOURNAL_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    line = journal_line(day, values)
    existing = path.read_text().splitlines() if path.exists() else [_header()]
    kept = [row for row in existing if not row.startswith(f"{day}\t")]
    if not kept or kept[0] != _header():
        kept = [_header(), *(row for row in kept if row != _header())]
    kept.append(line)
    body = [kept[0], *sorted(kept[1:])]
    path.write_text("\n".join(body) + "\n")
    return path


def read_journal(data_dir: str | Path) -> list[JournalEntry]:
    """Every run recorded so far, oldest first."""
    path = Path(data_dir) / JOURNAL_NAME
    if not path.exists():
        return []
    rows = path.read_text().splitlines()[1:]
    entries = []
    for row in rows:
        if not row.strip():
            continue
        day, *cells = row.split("\t")
        entries.append(JournalEntry(day, tuple(cells)))
    return entries
