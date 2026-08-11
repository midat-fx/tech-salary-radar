"""The day's rows, shaped for a browser to download and filter.

The dashboard filters client-side over every open posting, so this file is the
one the visitor actually waits for. Two decisions keep it small enough to be
worth downloading:

**Indices instead of strings.** Company and skill names repeat across thousands
of rows; storing an index into a shared list turns a 200-byte row into a 40-byte
one. The lists are built in first-seen order rather than sorted, because the
order is an implementation detail and sorting would only make diffs look tidier
in a file nobody reads by hand.

**A null skills field, not an empty one.** ``null`` means the posting was never
labelled and ``[]`` means it was labelled and nothing was found — the same
distinction ADR 0003 rests on, carried all the way to the browser so the site
can say "not yet analysed" instead of "no skills".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from etl.aggregate.labels import labels_for

__all__ = ["SnapshotPayload", "Interner", "build_snapshot"]

_SQL = """
    SELECT s.job_uid, s.region, s.seniority, s.is_remote, s.is_management, s.company,
           s.salary_mid_usd, j.first_seen
    FROM snap s
    LEFT JOIN (SELECT job_uid, min(first_seen) first_seen FROM jobs GROUP BY 1) j USING(job_uid)
    WHERE s.snapshot_date = ?
"""


@dataclass
class Interner:
    """First-seen order string pool. ``index("acme") -> 0``."""

    values: list[str] = field(default_factory=list)
    _seen: dict[str, int] = field(default_factory=dict)

    def index(self, value: str) -> int:
        if value not in self._seen:
            self._seen[value] = len(self.values)
            self.values.append(value)
        return self._seen[value]

    def __len__(self) -> int:
        return len(self.values)


@dataclass(frozen=True)
class SnapshotPayload:
    """What ``latest.json`` contains."""

    snapshot_date: str
    companies: list[str]
    skills: list[str]
    rows: list[list]

    def as_dict(self) -> dict:
        return {
            "snapshot_date": self.snapshot_date,
            "companies": self.companies,
            "skills": self.skills,
            "rows": self.rows,
        }

    @property
    def size(self) -> int:
        return len(self.rows)


def build_snapshot(con, latest_date) -> SnapshotPayload:
    """One row per open posting on ``latest_date``."""
    rows = con.execute(_SQL, [latest_date]).fetchall()
    index = labels_for(con, [row[0] for row in rows])
    companies, skills = Interner(), Interner()

    out: list[list] = []
    for uid, region, seniority, remote, management, company, salary, first_seen in rows:
        if index.was_read(uid):
            skill_field = [skills.index(name) for name in sorted(index.skills(uid))]
        else:
            skill_field = None
        is_new = 1 if (first_seen is not None and str(first_seen) == str(latest_date)) else 0
        out.append(
            [
                region,
                seniority,
                int(bool(remote)),
                int(bool(management)),
                companies.index(company),
                salary,
                skill_field,
                is_new,
            ]
        )
    return SnapshotPayload(str(latest_date), companies.values, skills.values, out)
