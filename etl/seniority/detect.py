"""Read a level out of a title, in the order the failure modes were found.

Precedence, and the reason for each step:

1. **Member of Technical Staff first.** It contains "staff" and is an IC title.
   Left to the word list, every AI lab's whole engineering org becomes staff+.
2. **Words before numerals.** "Senior Engineer II" is senior; the roman numeral
   is a sub-level inside it.
3. **The role-anchored numeral only.** "Engineer II" is mid. A numeral that is
   not attached to the role noun, or a company ladder code, is not read at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from etl.seniority.levels import Seniority
from etl.seniority.titles import (
    AMBIGUOUS_NUMERAL,
    JUNIOR,
    MANAGEMENT,
    MID,
    MID_NUMERAL,
    MTS,
    SENIOR,
    STAFF,
)

__all__ = ["Reading", "detect_seniority", "seniority_of", "is_management"]


@dataclass(frozen=True)
class Reading:
    """The level, and which rule produced it."""

    seniority: Seniority
    rule: str

    @property
    def value(self) -> str:
        return self.seniority.value


def detect_seniority(title: str | None) -> Reading:
    """Level and the rule that decided it."""
    text = title or ""
    if not text.strip():
        return Reading(Seniority.UNSPECIFIED, "empty")

    if MTS.search(text):
        # An IC title that happens to contain "staff". "Senior MTS" is still
        # senior, so the senior word is checked inside this branch rather than
        # the branch being an unconditional dead end.
        if SENIOR.search(text):
            return Reading(Seniority.SENIOR, "mts-senior")
        return Reading(Seniority.UNSPECIFIED, "mts")
    if STAFF.search(text):
        return Reading(Seniority.STAFF_PLUS, "staff-word")
    if SENIOR.search(text):
        return Reading(Seniority.SENIOR, "senior-word")
    if JUNIOR.search(text):
        return Reading(Seniority.JUNIOR, "junior-word")
    if MID.search(text):
        return Reading(Seniority.MID, "mid-word")
    if MID_NUMERAL.search(text) and not AMBIGUOUS_NUMERAL.search(text):
        return Reading(Seniority.MID, "role-numeral")
    if AMBIGUOUS_NUMERAL.search(text):
        # A level the employer knows and the reader does not.
        return Reading(Seniority.UNSPECIFIED, "ambiguous-numeral")
    return Reading(Seniority.UNSPECIFIED, "no-marker")


def seniority_of(title: str | None) -> str:
    """The stored bucket for a title."""
    return detect_seniority(title).value


def is_management(title: str | None) -> bool:
    """True for Manager/Director/VP/Head/Chief roles.

    Excluded from every salary statistic rather than bucketed: management pay is
    a different distribution with a different shape, and mixing it moves the
    senior median without any of the samples changing.
    """
    return bool(MANAGEMENT.search(title or ""))
