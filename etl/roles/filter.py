"""Whether a posting belongs in the salary statistics at all.

The order of the four checks is the entire content of this module, and it is
asymmetric because the errors are asymmetric.

1. **Hard deny wins outright.** "Solutions Engineer" and "Technical Program
   Manager" both match the allow list, and both are sales and project work.
   Nothing rescues a hard deny.
2. **An allow signal beats a soft deny.** "Data Engineer, Marketing Analytics"
   is an engineering job in a marketing team. Reading the soft deny first would
   drop it.
3. **A soft deny with no allow signal drops the posting.** "Marketing Manager"
   has nothing technical in it.
4. **A tech department is the last resort.** Titles like "Member of Technical
   Staff" or a bare "Analyst" say little; the department is weaker evidence and
   is only consulted when the title said nothing.

Letting a non-technical role through costs more than dropping a technical one.
The dropped posting is one row out of six thousand; the admitted one is a
different pay distribution mixed into every median that follows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from etl.roles.patterns import ALLOW, HARD_DENY, SOFT_DENY, TECH_DEPARTMENT

__all__ = ["Decision", "RoleVerdict", "classify_role", "passes_role_filter"]


class Decision(str, Enum):
    """Why a posting was kept or dropped. Counted in the run report: a shift
    means a board changed how it words its titles."""

    HARD_DENIED = "hard-denied"
    ALLOWED_BY_TITLE = "allowed-by-title"
    SOFT_DENIED = "soft-denied"
    ALLOWED_BY_DEPARTMENT = "allowed-by-department"
    NO_SIGNAL = "no-signal"
    """Nothing matched anywhere. Dropped, because admitting an unclassifiable
    posting mixes an unknown population into the medians."""


@dataclass(frozen=True)
class RoleVerdict:
    keep: bool
    decision: Decision

    def __bool__(self) -> bool:
        return self.keep


def classify_role(title: str | None, department: str | None = None) -> RoleVerdict:
    """The decision and the rule that produced it."""
    text = title or ""
    if HARD_DENY.search(text):
        return RoleVerdict(False, Decision.HARD_DENIED)
    if ALLOW.search(text):
        return RoleVerdict(True, Decision.ALLOWED_BY_TITLE)
    if SOFT_DENY.search(text):
        return RoleVerdict(False, Decision.SOFT_DENIED)
    if department and TECH_DEPARTMENT.search(department):
        return RoleVerdict(True, Decision.ALLOWED_BY_DEPARTMENT)
    return RoleVerdict(False, Decision.NO_SIGNAL)


def passes_role_filter(title: str | None, department: str | None = None) -> bool:
    """True when the posting is a technical individual-contributor role."""
    return classify_role(title, department).keep
