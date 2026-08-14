"""Turning aggregates into the files the site downloads.

Separated from the aggregation because the two fail differently: an aggregation
bug produces a wrong number, a publication bug produces a file the browser
cannot read or a diff on every run. The second is invisible in a test of the
first.
"""

from etl.publish.parquet import (
    WriteResult,
    partition_path,
    read_partition,
    write_partition,
)
from etl.publish.badge import AMBER, GREEN, RED, Badge, eval_badge, jobs_badge
from etl.publish.revision import Kind, Revision, classify
from etl.publish.writer import SEPARATORS, dumps, would_change, write_json

__all__ = [
    "AMBER",
    "GREEN",
    "RED",
    "SEPARATORS",
    "Badge",
    "Kind",
    "Revision",
    "WriteResult",
    "classify",
    "dumps",
    "eval_badge",
    "jobs_badge",
    "partition_path",
    "read_partition",
    "would_change",
    "write_partition",
    "write_json",
]
