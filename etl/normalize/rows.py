"""Turn a fetched posting into the record every stored table is projected from.

One record per posting, built by asking each layer its question — where, what
level, is it management, is it a technical role, what does it pay — and then
projected into the snapshot and jobs shapes. The order does not matter here;
what matters is that each answer comes from the layer that owns it rather than
from a regex in this file, which is what it used to be.
"""

from __future__ import annotations

from etl.geo import read_remote, region_of
from etl.normalize.columns import JOB_COLUMNS, SNAPSHOT_COLUMNS, project
from etl.roles import passes_role_filter
from etl.salary import normalize_salary
from etl.schema import job_uid
from etl.seniority import is_management, seniority_of

__all__ = ["normalize_job", "build_records", "normalize_all", "build_snapshot_rows"]


def normalize_job(job: dict, rates, snapshot_date: str) -> dict:
    """The full record for one posting, assuming the role filter already passed."""
    title, location = job.get("title"), job.get("location_raw")
    return {
        "job_uid": job_uid(job["source"], job["company"], job["job_id"]),
        "snapshot_date": snapshot_date,
        "source": job["source"],
        "company": job["company"],
        "title": title,
        "location_raw": location,
        "region": region_of(location, job.get("country")),
        "is_remote": read_remote(job.get("is_remote"), location).value,
        "seniority": seniority_of(title),
        "is_management": is_management(title),
        "employment_type": job.get("employment_type"),
        "published_at": job.get("published_at"),
        "apply_url": job.get("apply_url"),
        **normalize_salary(job, rates),
    }


def build_records(jobs, rates, snapshot_date: str) -> tuple[list[dict], dict[str, int]]:
    """Filtered, de-duplicated-by-uid records, plus the counts worth reporting.

    The uid de-duplication here is within one board: the same posting returned
    twice by one API call, which happens. Cross-board de-duplication is a
    different question with a different key and lives in :mod:`etl.dedupe`.
    """
    seen: set[str] = set()
    records: list[dict] = []
    stats = {"filtered_non_tech": 0, "dropped_oob": 0, "duplicate_uids": 0}
    for job in jobs:
        if not passes_role_filter(job.get("title"), job.get("department")):
            stats["filtered_non_tech"] += 1
            continue
        record = normalize_job(job, rates, snapshot_date)
        if record["job_uid"] in seen:
            stats["duplicate_uids"] += 1
            continue
        seen.add(record["job_uid"])
        if record.get("dropped_oob"):
            stats["dropped_oob"] += 1
        records.append(record)
    return records, stats


def normalize_all(jobs, rates, snapshot_date: str, existing_uids) -> dict:
    """One pass -> the snapshot rows, the rows that are new, and the counts.

    A row is new when its uid has never been seen before. The caller excludes
    the current day's own partition from ``existing_uids``, so re-running a day
    reproduces its own "new" set instead of emptying it.
    """
    records, stats = build_records(jobs, rates, snapshot_date)
    snapshot_rows = [project(record, SNAPSHOT_COLUMNS) for record in records]
    new_rows = [
        {**project(record, JOB_COLUMNS), "first_seen": snapshot_date}
        for record in records
        if record["job_uid"] not in existing_uids
    ]
    return {"snapshot_rows": snapshot_rows, "new_rows": new_rows, "stats": stats}


def build_snapshot_rows(jobs, rates, snapshot_date: str):
    """Just the daily view, for callers that do not care about inflow."""
    records, stats = build_records(jobs, rates, snapshot_date)
    return [project(record, SNAPSHOT_COLUMNS) for record in records], stats
