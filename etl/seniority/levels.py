"""The seniority buckets, and the one that means "the title did not say".

Five values, four of which are levels and one of which is an admission. The
admission is the point: a title like ``Engineer L5`` or ``IC3`` carries a level
the employer knows and the reader does not, and mapping it to "senior" would be
inventing evidence. ADR 0006 records why those stay unspecified.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Seniority", "SENIORITIES", "ORDER", "is_ranked", "rank"]


class Seniority(str, Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF_PLUS = "staff+"
    UNSPECIFIED = "unspecified"
    """The title carried no level, or carried one that cannot be read across
    companies. A bucket, not a gap — it is large, and dropping it would remove
    most of Europe from every sample."""


SENIORITIES = tuple(s.value for s in Seniority)

#: Only the four real levels are ordered. ``unspecified`` deliberately has no
#: place in the order: sorting it anywhere implies it means something.
ORDER = (Seniority.JUNIOR, Seniority.MID, Seniority.SENIOR, Seniority.STAFF_PLUS)


def is_ranked(value: "Seniority | str") -> bool:
    """True for the four levels that can be compared with each other."""
    return _as(value) in ORDER


def rank(value: "Seniority | str") -> int | None:
    """Position in the ladder, or ``None`` for ``unspecified``.

    Returning ``None`` rather than a sentinel number is what stops a caller
    sorting the unspecified bucket to one end and reading meaning into it.
    """
    level = _as(value)
    return ORDER.index(level) if level in ORDER else None


def _as(value: "Seniority | str") -> Seniority:
    return value if isinstance(value, Seniority) else Seniority(str(value))
