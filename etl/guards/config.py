"""Check the configuration constants against each other before a run uses them.

Every constant in :mod:`etl.config` is defensible on its own; several are only
correct in relation to another. A daily job limit that is not a whole number of
batches wastes the tail of the budget. A plausibility floor above the ceiling
refuses every salary. An FX staleness window of zero marks a table stale the
moment it is written.

None of these fails loudly. They produce a run that finishes, writes a day, and
is quietly wrong — which is the failure mode this whole package exists for, so
the constants get the same treatment as the data.
"""

from __future__ import annotations

from etl.config import (
    FETCH_CIRCUIT_BREAK,
    FETCH_PAUSE_SEC,
    FX_MAX_AGE_DAYS,
    HOURS_PER_YEAR,
    HTTP_TIMEOUT,
    LLM_BATCH_SIZE,
    LLM_DAILY_JOB_LIMIT,
    LLM_TEXT_TRIM,
    MONTHS_PER_YEAR,
    SALARY_MAX_USD,
    SALARY_MIN_USD,
    WEEKS_PER_YEAR,
)
from etl.guards.verdict import Severity, Verdict

__all__ = ["check_config"]

#: Below this the model reads the company blurb and never reaches the
#: requirements. It was 1500 once, and the labels were unusable.
MIN_TEXT_TRIM = 2_000


def check_config() -> Verdict:
    """Everything that has to hold between two constants."""
    verdict = Verdict()

    if SALARY_MIN_USD >= SALARY_MAX_USD:
        verdict.add(
            "config",
            Severity.REFUSE,
            f"SALARY_MIN_USD {SALARY_MIN_USD} is not below SALARY_MAX_USD {SALARY_MAX_USD}",
        )

    if LLM_BATCH_SIZE <= 0:
        verdict.add("config", Severity.REFUSE, "LLM_BATCH_SIZE must be positive")
    elif LLM_DAILY_JOB_LIMIT % LLM_BATCH_SIZE:
        # The last batch of the day would be short, which wastes the tail of a
        # budget that is the binding constraint on coverage.
        verdict.add(
            "config",
            Severity.WARN,
            f"LLM_DAILY_JOB_LIMIT {LLM_DAILY_JOB_LIMIT} is not a whole number of "
            f"batches of {LLM_BATCH_SIZE}",
        )

    if LLM_TEXT_TRIM < MIN_TEXT_TRIM:
        verdict.add(
            "config",
            Severity.WARN,
            f"LLM_TEXT_TRIM {LLM_TEXT_TRIM} is below {MIN_TEXT_TRIM}: the requirements "
            "section of a long description lives past it",
        )

    if FX_MAX_AGE_DAYS < 1:
        verdict.add(
            "config",
            Severity.REFUSE,
            "FX_MAX_AGE_DAYS below 1 marks a rate table stale the moment it is written",
        )

    if FETCH_PAUSE_SEC < 0:
        verdict.add("config", Severity.REFUSE, "FETCH_PAUSE_SEC cannot be negative")
    if FETCH_CIRCUIT_BREAK < 2:
        verdict.add(
            "config",
            Severity.WARN,
            f"FETCH_CIRCUIT_BREAK {FETCH_CIRCUIT_BREAK} trips on almost any single failure",
        )
    if HTTP_TIMEOUT <= 0:
        verdict.add("config", Severity.REFUSE, "HTTP_TIMEOUT must be positive")

    # The working-year assumptions have to describe one year, or a daily rate
    # and an hourly rate for the same job stop agreeing.
    if HOURS_PER_YEAR != 40 * WEEKS_PER_YEAR:
        verdict.add(
            "config",
            Severity.WARN,
            f"HOURS_PER_YEAR {HOURS_PER_YEAR} is not 40 x WEEKS_PER_YEAR {WEEKS_PER_YEAR}",
        )
    if MONTHS_PER_YEAR != 12:
        verdict.add("config", Severity.REFUSE, "MONTHS_PER_YEAR must be 12")

    return verdict
