"""Skill extraction: the catalog, the prompt, the queue, the cache and the score.

The boards carry no structured skills field, so every label here comes from a
language model reading a job description. That makes two things matter more
than the extraction itself: the difference between "labelled, found nothing"
and "never labelled" (ADR 0003), and which postings get the day's finite budget
(:mod:`etl.skills.queue`).
"""

from etl.skills.cache import CacheState, processed_uids, read_cache_state
from etl.skills.catalog import ALIAS_TO_CANON, CANONICAL, SKILLS, canonicalize
from etl.skills.client import GeminiUnavailable, gemini_call
from etl.skills.extract import (
    MAX_FAILURES,
    QUOTA_PATTERN,
    ExtractionStats,
    build_queue,
    extract_batch,
    extract_for_jobs,
)
from etl.skills.prompt import PROMPT, PROMPT_VERSION, RESPONSE_SCHEMA, VERSION_HISTORY
from etl.skills.quality import LabelIssue, Score, lint_labels, score_labels
from etl.skills.queue import Candidate, prioritise

__all__ = [
    "ALIAS_TO_CANON",
    "CANONICAL",
    "MAX_FAILURES",
    "PROMPT",
    "PROMPT_VERSION",
    "QUOTA_PATTERN",
    "RESPONSE_SCHEMA",
    "SKILLS",
    "VERSION_HISTORY",
    "CacheState",
    "Candidate",
    "ExtractionStats",
    "GeminiUnavailable",
    "LabelIssue",
    "Score",
    "build_queue",
    "canonicalize",
    "extract_batch",
    "extract_for_jobs",
    "gemini_call",
    "lint_labels",
    "prioritise",
    "processed_uids",
    "read_cache_state",
    "score_labels",
]
