"""The daily run as named stages, in the order they must happen.

The order is not arbitrary and three of the four adjacencies are load-bearing:

* **fetch before rates.** The crawl is the long part; fetching rates first would
  age them by the length of the crawl for no benefit.
* **normalise before de-duplication.** The fingerprint is built from normalised
  fields — region, seniority, tidied location — so de-duplicating raw postings
  would compare two spellings of one city and find them different.
* **de-duplication before the guards.** The volume guard compares today against
  history; comparing de-duplicated rows against non-de-duplicated ones would
  read the correction as a collapse and refuse the first correct day.
* **guards before the write.** The whole point: nothing is written until the day
  has been judged.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

__all__ = ["StageResult", "STAGE_ORDER", "by_source"]

#: The names a run reports progress under. Fixed so a log can be read by
#: somebody who has not read this file.
STAGE_ORDER = ("fetch", "rates", "normalise", "dedupe", "guard", "write", "skills", "report")


@dataclass
class StageResult:
    """What one stage produced, and what it wants said about it."""

    name: str
    ok: bool = True
    detail: str = ""
    values: dict = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.ok

    def describe(self) -> str:
        return f"{self.name}: {self.detail}" if self.detail else self.name


def by_source(rows: list[dict]) -> dict[str, int]:
    """Row counts per board — the shape the volume guard compares against."""
    return dict(Counter(row["source"] for row in rows))
