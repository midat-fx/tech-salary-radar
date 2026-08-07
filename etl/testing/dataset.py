"""Build a plausible parquet history in a temp directory, in one call.

Every test of the aggregator, the guards or the publisher needs days of
snapshots to read, and each one used to build them by hand — which is how the
fixtures ended up writing a ``jobs`` partition with two of twenty-one columns
and job_uids that were not ``source:company:job_id``.

The builder produces rows that satisfy the schema, so a test that passes here
would also pass against the writer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from etl.schema import JOBS, SKILLS, SNAPSHOTS

__all__ = ["JobSpec", "DatasetBuilder", "build_dataset"]


@dataclass
class JobSpec:
    """One posting, in the terms a test cares about."""

    uid: str
    salary: float | None = None
    seniority: str = "senior"
    region: str = "us"
    source: str = "ashby"
    company: str = "acme"
    remote: bool = False
    management: bool = False
    skills: list[str] | None = None
    """``None`` means never labelled; ``[]`` means labelled and nothing found.
    The distinction is the whole of ADR 0003, so the fake has to carry it."""

    def snapshot_row(self, day: str) -> dict:
        return {
            "job_uid": self.uid,
            "snapshot_date": day,
            "source": self.source,
            "company": self.company,
            "region": self.region,
            "is_remote": self.remote,
            "seniority": self.seniority,
            "is_management": self.management,
            "salary_min_usd": self.salary,
            "salary_max_usd": self.salary,
            "salary_mid_usd": self.salary,
            "has_salary": self.salary is not None,
            "employment_type": "FullTime",
            "published_at": "2026-08-01T00:00:00+00:00",
        }

    def job_row(self, first_seen: str) -> dict:
        return {
            "job_uid": self.uid,
            "first_seen": first_seen,
            "source": self.source,
            "company": self.company,
            "title": "Backend Engineer",
            "location_raw": "Remote" if self.remote else "Berlin, Germany",
            "region": self.region,
            "is_remote": self.remote,
            "seniority": self.seniority,
            "is_management": self.management,
            "employment_type": "FullTime",
            "published_at": "2026-08-01T00:00:00+00:00",
            "apply_url": None,
            "currency_original": "USD" if self.salary else None,
            "salary_min_orig": self.salary,
            "salary_max_orig": self.salary,
            "salary_interval_orig": "year",
            "salary_min_usd": self.salary,
            "salary_max_usd": self.salary,
            "salary_mid_usd": self.salary,
            "has_salary": self.salary is not None,
        }

    def skill_rows(self, day: str, prompt_version: str = "v1") -> list[dict]:
        if self.skills is None:
            return []
        labels = self.skills or [None]
        return [
            {
                "job_uid": self.uid,
                "skill": label,
                "source": "llm",
                "prompt_version": prompt_version,
                "extracted_at": f"{day}T00:00:00Z",
            }
            for label in labels
        ]


@dataclass
class DatasetBuilder:
    """Accumulate days, then write them all as parquet partitions."""

    root: Path
    days: dict[str, list[JobSpec]] = field(default_factory=dict)
    prompt_version: str = "v1"

    def day(self, date: str, jobs: list[JobSpec]) -> "DatasetBuilder":
        self.days[date] = jobs
        return self

    def write(self):
        """Write every partition and return a DuckDB connection over the result."""
        from etl.normalize import write_partition

        first_seen: dict[str, str] = {}
        for date in sorted(self.days):
            jobs = self.days[date]
            write_partition([j.snapshot_row(date) for j in jobs], self.root, SNAPSHOTS.name, date)
            fresh = [j for j in jobs if j.uid not in first_seen]
            for job in fresh:
                first_seen[job.uid] = date
            if fresh:
                write_partition([j.job_row(date) for j in fresh], self.root, JOBS.name, date)
            skills = [row for j in jobs for row in j.skill_rows(date, self.prompt_version)]
            if skills:
                write_partition(skills, self.root, SKILLS.name, date)
        from etl.aggregate import _con

        return _con(str(self.root))


def build_dataset(root: Path, days: dict[str, list[JobSpec]], prompt_version: str = "v1"):
    """One-liner for the common case: a dict of day -> jobs."""
    builder = DatasetBuilder(root, prompt_version=prompt_version)
    for date, jobs in days.items():
        builder.day(date, jobs)
    return builder.write()
