"""Seniority: four levels, one admission, and the management exclusion.

The admission — ``unspecified`` — is the load-bearing part. See ADR 0006.
"""

from etl.seniority.detect import Reading, detect_seniority, is_management, seniority_of
from etl.seniority.levels import ORDER, SENIORITIES, Seniority, is_ranked, rank
from etl.seniority.titles import AMBIGUOUS_NUMERAL, MANAGEMENT, MID_NUMERAL

__all__ = [
    "AMBIGUOUS_NUMERAL",
    "MANAGEMENT",
    "MID_NUMERAL",
    "ORDER",
    "SENIORITIES",
    "Reading",
    "Seniority",
    "detect_seniority",
    "is_management",
    "is_ranked",
    "rank",
    "seniority_of",
]
