"""What counts as a technical individual-contributor role.

The filter that decides what the salary statistics are *about*. Management is
excluded separately, by :mod:`etl.seniority` — this package answers whether the
posting is engineering at all, not what level it is.
"""

from etl.roles.filter import Decision, RoleVerdict, classify_role, passes_role_filter
from etl.roles.patterns import ALLOW, HARD_DENY, SOFT_DENY, TECH_DEPARTMENT

__all__ = [
    "ALLOW",
    "HARD_DENY",
    "SOFT_DENY",
    "TECH_DEPARTMENT",
    "Decision",
    "RoleVerdict",
    "classify_role",
    "passes_role_filter",
]
