"""Years of experience, when a posting states them.

A second signal about level, and a different kind of evidence from the title.
The title is what the company calls the role; the requirement is what it will
actually accept, and the two disagree in a way that matters: European postings
routinely say "Software Engineer" with "5+ years of experience" where an
American one would say "Senior Software Engineer" and state nothing.

That asymmetry is exactly where the `unspecified` bucket is largest (ADR 0006),
so this is the signal most likely to shrink it — which is why it is extracted
and stored rather than used to overwrite the title's answer. Overwriting would
be a methodology change made silently; keeping both lets it be evaluated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from etl.seniority.levels import Seniority

__all__ = ["ExperienceRequirement", "extract_experience", "level_from_years", "BANDS"]

#: "5+ years", "3-5 years", "at least 4 years", "minimum 2 years", "от 3 лет".
#: The unit is required: a bare number in a job advert is anything at all.
_PATTERNS = (
    re.compile(r"(\d{1,2})\s*\+\s*(?:years?|yrs?|лет|года?)", re.I),
    re.compile(r"(\d{1,2})\s*(?:-|–|—|to|до)\s*(\d{1,2})\s*(?:years?|yrs?|лет|года?)", re.I),
    re.compile(
        r"(?:at least|minimum(?: of)?|min\.?|от)\s*(\d{1,2})\s*(?:years?|yrs?|лет|года?)", re.I
    ),
    re.compile(r"(\d{1,2})\s*(?:years?|yrs?|лет|года?)\s*(?:of\s+)?(?:relevant\s+)?experience", re.I),
)

#: Phrases that carry a number of years and are not a requirement. "10 years of
#: company history" and "3 years of runway" both parse as a seniority signal
#: without this.
_NOT_A_REQUIREMENT = re.compile(
    r"\b(?:founded|history|runway|anniversary|in business|track record of)\b", re.I
)

#: An upper bound on what a job advert can plausibly ask for. Above it the match
#: is almost always a company age or a contract length.
MAX_YEARS = 20

#: Years -> level. The boundaries are the ones these postings actually use, and
#: they are coarse on purpose: nobody's ladder is precise to a year.
BANDS: tuple[tuple[int, Seniority], ...] = (
    (2, Seniority.JUNIOR),
    (5, Seniority.MID),
    (8, Seniority.SENIOR),
    (MAX_YEARS, Seniority.STAFF_PLUS),
)


@dataclass(frozen=True)
class ExperienceRequirement:
    """What a posting asked for, and the level that implies."""

    years: int
    #: The upper end when the posting gave a range ("3-5 years").
    years_max: int | None = None
    source: str = "text"

    @property
    def level(self) -> Seniority:
        return level_from_years(self.years)

    def describe(self) -> str:
        span = f"{self.years}-{self.years_max}" if self.years_max else f"{self.years}+"
        return f"{span} years -> {self.level.value}"


def level_from_years(years: int) -> Seniority:
    """The band a requirement falls in.

    Uses the *lower* end of a stated range: "3-5 years" is a posting that will
    take three, and treating it as five would push a whole class of European
    mid-level adverts into senior.
    """
    for threshold, level in BANDS:
        if years < threshold:
            return level
    return Seniority.STAFF_PLUS


def extract_experience(text: str | None) -> ExperienceRequirement | None:
    """The first plausible requirement in a description, or ``None``.

    First rather than smallest: requirements sections lead with the headline
    ask, and a later "2 years with Kubernetes" is about one tool rather than the
    role.
    """
    if not text:
        return None
    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            window = text[max(0, match.start() - 60) : match.end() + 40]
            if _NOT_A_REQUIREMENT.search(window):
                continue
            groups = [int(group) for group in match.groups() if group]
            if not groups or groups[0] > MAX_YEARS:
                continue
            low = groups[0]
            high = groups[1] if len(groups) > 1 and groups[1] <= MAX_YEARS else None
            return ExperienceRequirement(low, high)
    return None
