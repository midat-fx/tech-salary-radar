"""The title patterns, and why each one is shaped the way it is.

Every pattern here was added because a real title was read wrongly without it.
They are kept apart from the matching order in :mod:`etl.seniority.detect` so
that adding a word and changing the precedence stay separate decisions.
"""

from __future__ import annotations

import re

__all__ = [
    "STAFF",
    "SENIOR",
    "JUNIOR",
    "MID",
    "MID_NUMERAL",
    "AMBIGUOUS_NUMERAL",
    "MANAGEMENT",
    "MTS",
]

STAFF = re.compile(r"\b(staff|principal|lead|distinguished|fellow)\b", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|snr)\b", re.I)
JUNIOR = re.compile(
    r"\b(junior|jr\.?|intern|internship|new grad|graduate|entry[- ]level|apprentice|associate)\b",
    re.I,
)
MID = re.compile(r"\b(mid|middle|mid[- ]level|intermediate)\b", re.I)

#: "Software Engineer II" / "Data Analyst 2": a level numeral directly after the
#: role noun. Anchored to the noun because a bare "II" elsewhere in a title is
#: as likely to be a product name as a level.
MID_NUMERAL = re.compile(
    r"\b(engineer|developer|analyst|scientist|programmer)\b[\s,|-]*\b(?:ii|2)\b", re.I
)

#: Two numerals ("Engineer 1 - 2") or a company ladder code (L5, IC3, E4). These
#: are levels, but not ones that mean the same thing at two companies, so they
#: resolve to unspecified rather than to a guess. See ADR 0006.
AMBIGUOUS_NUMERAL = re.compile(
    r"\b(?:i{1,3}v?|iv|\d)\b[\s,|-]*\b(?:i{1,3}v?|iv|\d)\b|\b(?:l\d|ic\d|e\d)\b", re.I
)

MANAGEMENT = re.compile(
    r"\b(manager|director|vp|vice president|head of|chief|cto|ceo|cio|cfo|coo)\b", re.I
)

#: "Member of Technical Staff" is an AI-lab individual-contributor title. It
#: contains the word "staff" and is not a staff-level role, which is exactly the
#: kind of collision a word list cannot resolve on its own.
MTS = re.compile(r"member of technical staff|\bmts\b", re.I)
