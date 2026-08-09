"""One row per job, when the same job is advertised on two boards.

``job_uid`` identifies a *posting*; this package identifies a *job*. The
difference is a real number on the site: a company running both Greenhouse and
Lever has its openings counted twice, and each one contributes twice to the
median. See ADR 0009.
"""

from etl.dedupe.detect import DedupeReport, deduplicate, group_by_fingerprint
from etl.dedupe.fingerprint import Fingerprint, fingerprint, normalise_title
from etl.dedupe.merge import FILLABLE, IDENTITY, MergedJob, merge_group
from etl.dedupe.priority import SOURCE_RANK, better_of, rank_of, sort_candidates

__all__ = [
    "FILLABLE",
    "IDENTITY",
    "SOURCE_RANK",
    "DedupeReport",
    "Fingerprint",
    "MergedJob",
    "better_of",
    "deduplicate",
    "fingerprint",
    "group_by_fingerprint",
    "merge_group",
    "normalise_title",
    "rank_of",
    "sort_candidates",
]
