"""Turn normalized jobs into snapshot / new-job rows and write daily parquet partitions (stage 2)."""

import re

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from etl.salary import normalize_salary

_EU = re.compile(r"\b(united kingdom|england|scotland|wales|ireland|london|germany|berlin|munich|"
                 r"france|paris|spain|madrid|barcelona|netherlands|amsterdam|poland|warsaw|krakow|"
                 r"sweden|stockholm|portugal|lisbon|porto|italy|rome|milan|belgium|brussels|austria|"
                 r"vienna|denmark|copenhagen|finland|helsinki|norway|oslo|czech|prague|romania|"
                 r"bucharest|estonia|tallinn|lithuania|latvia|greece|athens|hungary|budapest|"
                 r"switzerland|zurich|zürich|luxembourg|bulgaria|croatia|slovakia|slovenia|"
                 r"emea|europe|\beu\b|\buk\b)\b", re.I)
_US = re.compile(r"\b(united states|u\.s\.a?|\busa?\b|california|new york|texas|washington|"
                 r"massachusetts|illinois|georgia|colorado|florida|san francisco|seattle|austin|"
                 r"boston|chicago|los angeles|denver|atlanta|new jersey|virginia|oregon|arizona|"
                 r"ca|ny|tx|wa|ma|il|ga|co|fl)\b", re.I)

_STAFF = re.compile(r"\b(staff|principal|lead|distinguished|fellow)\b", re.I)
_SENIOR = re.compile(r"\b(senior|sr\.?|snr)\b", re.I)
_JUNIOR = re.compile(r"\b(junior|jr\.?|intern|internship|new grad|graduate|entry[- ]level|apprentice|"
                     r"associate)\b", re.I)
_MID = re.compile(r"\b(mid|middle|mid[- ]level|intermediate)\b", re.I)

_MGMT = re.compile(r"\b(manager|director|vp|vice president|head of|chief|cto|ceo|cio|cfo|coo)\b", re.I)

# hard deny wins over an allow-signal (eng-adjacent-but-not-dev, PM, design)
_HARD_DENY = re.compile(r"\b(product manager|program manager|product owner|technical program|"
                        r"designer|ux designer|ui designer|product designer|graphic designer|"
                        r"design lead|sales engineer|solutions engineer|solutions consultant|"
                        r"sales development|account executive|account manager)\b", re.I)
# soft deny only applies when the title carries NO allow (tech) signal
_SOFT_DENY = re.compile(r"\b(sales|recruit|talent|\bhr\b|people ops|human resources|legal|counsel|"
                        r"finance|accounting|marketing|content|community|customer success|"
                        r"customer support|\bsupport\b|\boffice\b|coordinator|facilities|"
                        r"executive assistant|administrative|receptionist)\b", re.I)
_ALLOW_ROLE = re.compile(r"\b(engineer|engineering|developer|programmer|software|backend|back[- ]end|"
                         r"front[- ]?end|full[- ]?stack|sde|mobile|android|ios|data|machine learning|"
                         r"\bml\b|\bai\b|mlops|devops|sre|site reliability|platform|infrastructure|"
                         r"cloud|\bqa\b|quality assurance|sdet|test engineer|security|infosec|"
                         r"applied scientist|research engineer|research scientist|analytics)\b", re.I)
_TECH_DEPT = re.compile(r"engineering|data|infrastructure|platform|security|technolog|research|r&d",
                        re.I)


def job_uid(source, company, job_id):
    """Stable dedup key: f'{source}:{company}:{job_id}'."""
    return f"{source}:{company}:{job_id}"


def region_of(location_raw, country=None):
    """Map a location to region bucket: us | eu | other (PLAN.md §3.6). EU wins ties."""
    text = f"{location_raw or ''} {country or ''}"
    if _EU.search(text):
        return "eu"
    if _US.search(text):
        return "us"
    return "other"


def seniority_of(title):
    """Heuristic seniority from title: staff+ | senior | junior | mid | unspecified (PLAN.md §3.6)."""
    t = title or ""
    if _STAFF.search(t):
        return "staff+"
    if _SENIOR.search(t):
        return "senior"
    if _JUNIOR.search(t):
        return "junior"
    if _MID.search(t):
        return "mid"
    return "unspecified"


def is_management(title):
    """True for Manager/Director/VP/Head/Chief roles (excluded from salary stats, PLAN.md §3.6)."""
    return bool(_MGMT.search(title or ""))


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
        "is_remote": bool(job.get("is_remote")),
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


def write_partition(rows, data_dir, table, dt):
    """Write a daily parquet partition (zstd, sorted by job_uid); overwrites the whole day."""
    from pathlib import Path
    out = Path(data_dir) / table / f"dt={dt}" / "part.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if not df.empty and "job_uid" in df:
        df = df.sort_values("job_uid").reset_index(drop=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out, compression="zstd")
    return out
