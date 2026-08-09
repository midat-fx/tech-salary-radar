"""The key that says two postings are the same job on two boards.

``job_uid`` cannot do it: it is ``source:company:job_id``, so the same role
advertised on Greenhouse and on Lever has two different ones by construction.
That is correct for the uid — it identifies a *posting* — and it is why a second
key is needed to identify a *job*.

What is actually available to key on: the company, the title, and the location.
Not the description (boards trim it differently), not the salary (often absent
on one side), not the publish date (the boards disagree by days).

The fingerprint is deliberately lossy in one direction only. It must never
merge two genuinely different roles, because that deletes a real posting from
the market count. Missing a duplicate is the cheaper error: it inflates the
count slightly, which is what already happens today.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from etl.geo import location_tokens, normalise_location
from etl.seniority import seniority_of

__all__ = ["Fingerprint", "fingerprint", "normalise_title", "TITLE_NOISE"]

#: Words that decorate a title without changing which job it is. Removing them
#: is what lets "Senior Backend Engineer (Remote)" and "Senior Backend Engineer
#: - Platform Team" meet. The level words are *not* here: seniority is carried
#: in the fingerprint separately, so "Senior Engineer" never meets "Engineer".
TITLE_NOISE = re.compile(
    r"\b(remote|hybrid|on-?site|contract|full[- ]?time|part[- ]?time|permanent|"
    r"m/f/d|m/w/d|f/m/d|all genders|w/m/d|h/f)\b",
    re.I,
)
_BRACKETED = re.compile(r"[\(\[][^\)\]]*[\)\]]")
_PUNCT = re.compile(r"[^\w\s+#.]+")
_WS = re.compile(r"\s+")


def normalise_title(title: str | None) -> str:
    """Strip decoration, keep the words that name the role.

    ``+`` and ``#`` survive the punctuation strip because ``C++`` and ``C#`` are
    role names, and collapsing them to ``c`` would merge two different jobs —
    the one error this must not make.
    """
    if not title:
        return ""
    text = _BRACKETED.sub(" ", title)
    text = TITLE_NOISE.sub(" ", text)
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip().casefold()


@dataclass(frozen=True)
class Fingerprint:
    """What has to match for two postings to be the same job."""

    company: str
    title: str
    seniority: str
    place: tuple[str, ...]

    def __str__(self) -> str:
        where = "/".join(self.place) or "-"
        return f"{self.company}|{self.title}|{self.seniority}|{where}"

    @property
    def is_usable(self) -> bool:
        """A fingerprint with no company or no title cannot identify anything.

        Both happen: a board can serve a posting with an empty title, and the
        company slug is missing when a seed entry was hand-edited. Such a
        posting is left alone rather than merged with every other broken one.
        """
        return bool(self.company and self.title)


def fingerprint(row: dict) -> Fingerprint:
    """The key for one posting.

    Company is the board slug rather than the display name: the display name is
    written by whoever set the board up and differs across ATSs, while the slug
    is stable within one and the same across the two the company runs — which is
    exactly the case being detected.
    """
    company = (row.get("company") or "").strip().casefold()
    title = normalise_title(row.get("title"))
    level = row.get("seniority") or seniority_of(row.get("title"))
    place = location_tokens(row.get("location_raw")) or (
        (normalise_location(row.get("region")),) if row.get("region") else ()
    )
    return Fingerprint(company, title, level, place)
