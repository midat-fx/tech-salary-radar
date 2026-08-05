"""Turn normalized jobs into snapshot / new-job rows and write daily parquet partitions (stage 2)."""

import re
from datetime import datetime

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from etl.geo import read_remote, region_of
from etl.salary import normalize_salary
from etl.schema import job_uid, table_for, validate_partition
from etl.seniority import is_management, seniority_of

# hard deny wins over an allow-signal (eng-adjacent-but-not-dev, PM, design, GTM)
_HARD_DENY = re.compile(r"\b(product manager|program manager|product owner|technical program|"
                        r"designer|ux designer|ui designer|product designer|graphic designer|"
                        r"design lead|sales engineer|solutions engineer|solutions consultant|"
                        r"solutions architect|sales development|account executive|account manager|"
                        r"partnerships|go[- ]to[- ]market|\bgtm\b|"
                        # data-annotation gig work: median ~$29k against a ~$221k IC median
                        r"labeler|labelling|annotator|data annotation)\b", re.I)
# soft deny only applies when the title carries NO allow (tech) signal
_SOFT_DENY = re.compile(r"\b(sales|recruit|talent|\bhr\b|people ops|human resources|legal|counsel|"
                        r"finance|accounting|marketing|content|community|customer success|"
                        r"customer support|\bsupport\b|\boffice\b|coordinator|facilities|"
                        r"executive assistant|administrative|receptionist)\b", re.I)
_ALLOW_ROLE = re.compile(r"\b(engineer|engineering|developer|programmer|software|backend|back[- ]end|"
                         r"front[- ]?end|full[- ]?stack|sde|mobile|android|ios|data|machine learning|"
                         r"\bml\b|\bai\b|mlops|devops|sre|site reliability|platform|infrastructure|"
                         r"cloud|\bqa\b|quality assurance|sdet|test engineer|security|infosec|"
                         r"applied scientist|research engineer|research scientist|analytics|"
                         r"member of technical staff|\bmts\b)\b", re.I)
_TECH_DEPT = re.compile(r"engineering|data|infrastructure|platform|security|technolog|research|r&d",
                        re.I)


def passes_role_filter(title, department=None):
    """Keep only tech-IC roles. hard-deny (PM/design/sales-eng) wins; else an allow (tech) signal
    wins over soft-deny (non-tech words); else a tech department keeps it (PLAN.md §3.7)."""
    t = title or ""
    if _HARD_DENY.search(t):
        return False
    if _ALLOW_ROLE.search(t):
        return True
    if _SOFT_DENY.search(t):
        return False
    if department and _TECH_DEPT.search(department):
        return True
    return False


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


def write_partition(rows, data_dir, table, dt, append=False, log=None):
    """Write a daily parquet partition (zstd, sorted by the table's key); overwrites the whole day.

    Every row is checked against the table specification first. A row that
    cannot be stored is dropped and counted rather than failing the day — one
    malformed posting out of six thousand must not cost the crawl — while a
    duplicate key still raises, because that means the pipeline built the day
    wrong rather than a board sending something odd.

    Empty rows -> no file (a columnless parquet is unreadable); a stale file for dt is removed.
    append=True keeps the rows already stored for dt: the skills cache grows across several
    runs of the same day, and each run only extracts what the anti-join left over.
    """
    from pathlib import Path
    spec = table_for(table)
    out = Path(data_dir) / table / f"dt={dt}" / "part.parquet"
    if append and out.exists():
        rows = pq.read_table(out).to_pylist() + list(rows)
    rows, rejected = validate_partition(spec, rows)
    if rejected and log:
        log(f"{table} {dt}: dropped {len(rejected)} unstorable rows, first: {rejected[0].reason}")
    if not rows:
        if out.exists():
            out.unlink()
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows).sort_values(list(spec.key)).reset_index(drop=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out, compression="zstd")
    return out


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
