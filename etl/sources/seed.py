"""The list of boards to crawl, and what makes an entry usable.

The seed is 320 hand-verified company boards, built once by a recon script and
committed. It is the only input to the crawl, so a malformed entry is not a
cosmetic problem: a wrong slug is a 404 every day forever, and a duplicate is
the same company counted twice in "companies tracked".

The file uses two spellings of the same field — ``ats`` in the entries the recon
script wrote, ``source`` in ones added by hand — which is exactly the kind of
drift that a loader should absorb once rather than every caller discovering.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from etl.config import SEED_PATH
from etl.schema.job import SOURCES

__all__ = ["SeedEntry", "SeedReport", "load_seed", "read_seed", "validate_seed"]


@dataclass(frozen=True)
class SeedEntry:
    """One board: which ATS hosts it, its slug there, and a human name."""

    source: str
    slug: str
    name: str

    def as_dict(self) -> dict[str, str]:
        return {"source": self.source, "slug": self.slug, "name": self.name}


@dataclass(frozen=True)
class SeedReport:
    """What the seed file contained, and what had to be dropped from it."""

    entries: tuple[SeedEntry, ...]
    inactive: int = 0
    unknown_source: tuple[str, ...] = ()
    duplicates: tuple[str, ...] = ()
    malformed: tuple[str, ...] = ()

    @property
    def usable(self) -> int:
        return len(self.entries)

    def describe(self) -> str:
        """One line for the run report; every number here is worth watching."""
        return (
            f"seed: {self.usable} boards"
            f" (skipped {self.inactive} inactive, {len(self.unknown_source)} unknown-ats,"
            f" {len(self.duplicates)} duplicate, {len(self.malformed)} malformed)"
        )


def read_seed(path: str | Path | None = None) -> list[dict]:
    """Raw JSON from the seed file. Kept separate so validation can be tested alone."""
    return json.loads(Path(path or SEED_PATH).read_text())


def validate_seed(raw: list[dict]) -> SeedReport:
    """Turn raw entries into usable ones, counting every reason for a drop.

    Only ``status == "active"`` entries are kept: the recon script marks a board
    inactive when it answered 404 or returned nothing, and re-checking those
    daily would spend a request per board for no rows.
    """
    entries: list[SeedEntry] = []
    seen: set[tuple[str, str]] = set()
    inactive = 0
    unknown: list[str] = []
    duplicates: list[str] = []
    malformed: list[str] = []

    for item in raw:
        if not isinstance(item, dict):
            malformed.append(repr(item)[:40])
            continue
        if item.get("status") != "active":
            inactive += 1
            continue
        source = item.get("ats") or item.get("source")
        slug = item.get("slug")
        if not source or not slug or not isinstance(slug, str):
            malformed.append(str(item.get("slug") or item.get("name") or item)[:40])
            continue
        if source not in SOURCES:
            unknown.append(f"{source}:{slug}")
            continue
        key = (source, slug)
        if key in seen:
            duplicates.append(f"{source}:{slug}")
            continue
        seen.add(key)
        entries.append(SeedEntry(source=source, slug=slug, name=item.get("name") or slug))

    return SeedReport(
        entries=tuple(entries),
        inactive=inactive,
        unknown_source=tuple(unknown),
        duplicates=tuple(duplicates),
        malformed=tuple(malformed),
    )


def load_seed(path: str | Path | None = None) -> list[dict]:
    """The crawl's input, in the dict shape the fetcher consumes."""
    return [entry.as_dict() for entry in validate_seed(read_seed(path)).entries]
