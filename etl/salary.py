"""Parse and normalize salary to annual gross USD (PLAN.md §5, stage 2).

Ashby: structured `compensation` components (Salary). Lever: `salaryRange` field.
Greenhouse: regex over description text (US pay-transparency, sparse).
"""


def parse_salary(job):
    """Extract {min, max, currency, interval} from a normalized job by its source, or None."""
    raise NotImplementedError


def to_annual(amount, interval):
    """Scale an amount to annual: hour x2080, week x52, month x12, year x1."""
    raise NotImplementedError


def normalize_salary(job, rates):
    """Full pipeline: parse -> annual -> USD -> mid (COALESCE) -> sanity bounds.

    Returns (salary_min_usd, salary_max_usd, salary_mid_usd, has_salary); out-of-bounds -> dropped.
    """
    raise NotImplementedError
