"""Fetched postings -> the rows the tables store.

Split from one flat module because the daily path and the one-off backfill are
different operations with different risks: one runs unattended every morning,
the other rewrites the whole inflow table and should be something a person
types.
"""

from etl.normalize.backfill import backfill_job_rows, publish_date
from etl.normalize.columns import JOB_COLUMNS, SNAPSHOT_COLUMNS, project
from etl.normalize.rows import (
    build_records,
    build_snapshot_rows,
    normalize_all,
    normalize_job,
)
from etl.publish.parquet import write_partition
from etl.roles import passes_role_filter
from etl.schema import job_uid
from etl.seniority import is_management, seniority_of
from etl.geo import region_of

__all__ = [
    "JOB_COLUMNS",
    "SNAPSHOT_COLUMNS",
    "backfill_job_rows",
    "build_records",
    "build_snapshot_rows",
    "is_management",
    "job_uid",
    "normalize_all",
    "normalize_job",
    "passes_role_filter",
    "project",
    "publish_date",
    "region_of",
    "seniority_of",
    "write_partition",
]
