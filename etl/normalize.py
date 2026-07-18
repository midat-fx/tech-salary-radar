"""Turn normalized jobs into snapshot / new-job rows and write daily parquet partitions (stage 2)."""


def job_uid(source, company, job_id):
    """Stable dedup key: f'{source}:{company}:{job_id}'."""
    raise NotImplementedError


def region_of(location_raw, country=None):
    """Map a location to region bucket: us | eu | other (PLAN.md §3.6)."""
    raise NotImplementedError


def seniority_of(title):
    """Heuristic seniority from title: junior | mid | senior | lead (PLAN.md §3.6)."""
    raise NotImplementedError


def build_snapshot_rows(jobs, rates):
    """Build thin snapshot rows for all active jobs found today (dedup by job_uid)."""
    raise NotImplementedError


def build_new_job_rows(jobs, rates):
    """Build full rows for job_uids first seen today (anti-join against data/jobs/*)."""
    raise NotImplementedError


def write_partition(rows, data_dir, table, dt):
    """Write a daily parquet partition (zstd), overwriting the whole day = idempotency."""
    raise NotImplementedError
