"""Which skills a posting carries, and which postings were never asked.

The distinction is the whole of ADR 0003 and it is easy to lose in SQL: a
``LEFT JOIN`` against the skills table returns a row with a null skill both for
a posting the model labelled and found nothing in, and for a posting nobody has
read. So the two are separated here, once, and every consumer takes the pair.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["LabelIndex", "labels_for"]

#: Only the newest prompt generation counts for a posting that carries several.
#: A premium computed across two prompts mixes two definitions of a skill.
_NEWEST_GENERATION = """
    SELECT job_uid, skill FROM (
        SELECT job_uid, skill, prompt_version,
               max(prompt_version) OVER (PARTITION BY job_uid) AS latest
        FROM sk WHERE job_uid IN (SELECT unnest(?))
    ) WHERE prompt_version = latest
"""


@dataclass(frozen=True)
class LabelIndex:
    """Skills per posting, and the set of postings that have been read at all."""

    by_uid: dict[str, set[str]]
    processed: set[str]

    def skills(self, uid: str) -> set[str]:
        return self.by_uid.get(uid, set())

    def was_read(self, uid: str) -> bool:
        """True when the model looked. False is not evidence a skill is absent."""
        return uid in self.processed

    @property
    def coverage(self) -> int:
        return len(self.processed)


def labels_for(con, uids: list[str]) -> LabelIndex:
    """Build the index for a set of postings in one query."""
    rows = con.execute(_NEWEST_GENERATION, [list(uids)]).fetchall() if uids else []
    by_uid: dict[str, set[str]] = {}
    processed: set[str] = set()
    for uid, skill in rows:
        processed.add(uid)
        if skill is not None:
            by_uid.setdefault(uid, set()).add(skill)
    return LabelIndex(by_uid, processed)
