"""Turn normalized jobs into snapshot / new-job rows and write daily parquet partitions (stage 2)."""

from datetime import datetime

from etl.geo import read_remote, region_of
from etl.publish.parquet import write_partition
from etl.roles import passes_role_filter
from etl.salary import normalize_salary
from etl.schema import job_uid
from etl.seniority import is_management, seniority_of

def normalize_job(job, rates, snapshot_date):
    """Full normalized record for one job (role-filter already passed)."""
    title, loc = job.get("title"), job.get("location_raw")
    sal = normalize_salary(job, rates)
    return {
        "job_uid": job_uid(job["source"], job["company"], job["job_id"]),
        "snapshot_date": snapshot_date,
        "source": job["source"], "company": job["company"],
        "title": title, "location_raw": loc,
        "region": region_of(loc, job.get("country")),
        "is_remote": read_remote(job.get("is_remote"), loc).value,
        "seniority": seniority_of(title), "is_management": is_management(title),
        "employment_type": job.get("employment_type"),
        "published_at": job.get("published_at"),
        "apply_url": job.get("apply_url"),
        **sal,
    }


_SNAP_COLS = ["job_uid", "snapshot_date", "source", "company", "region", "is_remote", "seniority",
              "is_management", "salary_min_usd", "salary_max_usd", "salary_mid_usd", "has_salary",
              "employment_type", "published_at"]
_JOB_COLS = ["job_uid", "first_seen", "source", "company", "title", "location_raw", "region",
             "is_remote", "seniority", "is_management", "employment_type", "published_at",
             "apply_url", "currency_original", "salary_min_orig", "salary_max_orig",
             "salary_interval_orig", "salary_min_usd", "salary_max_usd", "salary_mid_usd",
             "has_salary"]


def _records(jobs, rates, snapshot_date):
    """Role-filtered, deduped normalized records + stats {filtered_non_tech, dropped_oob}."""
    seen, recs, stats = set(), [], {"filtered_non_tech": 0, "dropped_oob": 0}
    for job in jobs:
        if not passes_role_filter(job.get("title"), job.get("department")):
            stats["filtered_non_tech"] += 1
            continue
        rec = normalize_job(job, rates, snapshot_date)
        if rec["job_uid"] in seen:
            continue
        seen.add(rec["job_uid"])
        if rec.get("dropped_oob"):
            stats["dropped_oob"] += 1
        recs.append(rec)
    return recs, stats


def normalize_all(jobs, rates, snapshot_date, existing_uids):
    """Single pass -> {snapshot_rows, new_rows, stats}. new_rows = job_uids not in existing_uids."""
    recs, stats = _records(jobs, rates, snapshot_date)
    snapshot_rows = [{k: r[k] for k in _SNAP_COLS} for r in recs]
    new_rows = [{**{k: r.get(k) for k in _JOB_COLS}, "first_seen": snapshot_date}
                for r in recs if r["job_uid"] not in existing_uids]
    return {"snapshot_rows": snapshot_rows, "new_rows": new_rows, "stats": stats}


def build_snapshot_rows(jobs, rates, snapshot_date):
    recs, stats = _records(jobs, rates, snapshot_date)
    return [{k: r[k] for k in _SNAP_COLS} for r in recs], stats


def _pub_date(published_at):
    if not published_at:
        return None
    try:
        return datetime.fromisoformat(str(published_at).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def backfill_job_rows(jobs, rates, today):
    """Group tech-IC deduped jobs into full rows keyed by first_seen = date(published_at) (§7 stage 4)."""
    recs, _ = _records(jobs, rates, today)
    by_date = {}
    for r in recs:
        fs = _pub_date(r.get("published_at")) or today
        row = {k: r.get(k) for k in _JOB_COLS}
        row["first_seen"] = fs
        by_date.setdefault(fs, []).append(row)
    return by_date



# Re-exported so callers keep one import for "turn a fetched job into a row".
# The rules themselves live in etl.geo and etl.seniority.
__all__ = [
    "backfill_job_rows",
    "build_snapshot_rows",
    "is_management",
    "job_uid",
    "normalize_all",
    "normalize_job",
    "passes_role_filter",
    "region_of",
    "seniority_of",
    "write_partition",
]
