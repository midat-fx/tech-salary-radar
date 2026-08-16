"""The stored contract: what a row contains, what it may not say, and which
version of that promise a given day was written under.

Import from here rather than from the submodules — the split between
``fields``, ``job``, ``validate`` and ``version`` is how the package is
organised, not a distinction callers should have to track.
"""

from etl.schema.errors import (
    InvariantViolated,
    MissingColumn,
    SchemaError,
    UnknownColumn,
    WrongType,
)
from etl.schema.fields import JOBS, SKILLS, SNAPSHOTS, TABLES, Field, Table, table_for
from etl.schema.job import (
    RAW_JOB_FIELDS,
    REGIONS,
    REQUIRED_RAW_FIELDS,
    SENIORITIES,
    SOURCES,
    RawJob,
    check_raw_job,
    job_uid,
    split_uid,
)
from etl.schema.migrations import (
    MARKER_COLUMN,
    PartitionRead,
    detect_version,
    read_partition_versioned,
)
from etl.schema.validate import (
    Rejected,
    check_invariants,
    coerce_row,
    fill_missing,
    validate_partition,
    validate_row,
    validate_rows,
)
from etl.schema.version import (
    HISTORY,
    SCHEMA_VERSION,
    Compatibility,
    SchemaVersion,
    compatibility,
    describe,
    is_readable,
)

__all__ = [
    "HISTORY",
    "JOBS",
    "RAW_JOB_FIELDS",
    "REGIONS",
    "REQUIRED_RAW_FIELDS",
    "SCHEMA_VERSION",
    "SENIORITIES",
    "SKILLS",
    "SNAPSHOTS",
    "SOURCES",
    "TABLES",
    "Compatibility",
    "Field",
    "InvariantViolated",
    "MARKER_COLUMN",
    "MissingColumn",
    "PartitionRead",
    "RawJob",
    "Rejected",
    "SchemaError",
    "SchemaVersion",
    "Table",
    "UnknownColumn",
    "WrongType",
    "check_invariants",
    "check_raw_job",
    "coerce_row",
    "compatibility",
    "describe",
    "detect_version",
    "read_partition_versioned",
    "fill_missing",
    "is_readable",
    "job_uid",
    "split_uid",
    "table_for",
    "validate_partition",
    "validate_row",
    "validate_rows",
]
