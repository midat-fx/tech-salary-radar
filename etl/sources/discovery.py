"""Build and re-check the seed: which candidate boards actually exist.

The seed was produced once by a script under ``probe-scripts/`` that did three
things worth keeping and one worth not. Worth keeping: probing a candidate slug
against each ATS, classifying what came back, and de-duplicating companies that
appear on more than one board. Worth losing: a hard-coded wall of company names,
a hand-rolled ``urllib`` client with its own User-Agent string, and a European
city list that had already drifted from the one in :mod:`etl.geo`.

This module is the kept part, on the real transport, with the real region rules
and no company names baked in. It is not run by the daily pipeline — the seed is
a deliberate, occasional act — but it is code the project depends on, so it
lives where it can be tested rather than in a directory nothing imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from etl.geo import Region, detect_region
from etl.schema.job import SOURCES
from etl.sources import PARSERS
from etl.sources.transport import get_json

__all__ = ["BoardStatus", "Probe", "probe_board", "classify_payload", "dedupe_candidates"]


class BoardStatus(str, Enum):
    ACTIVE = "active"
    """Answered, and has at least one posting. The only status the crawl uses."""

    EMPTY = "empty"
    """Answered with no postings. The board exists; the company is not hiring.
    Kept in the file rather than dropped, so a re-check knows it was seen."""

    DEAD = "dead"
    """404, or an answer that could not be parsed. The slug is wrong or gone."""


@dataclass(frozen=True)
class Probe:
    """What one candidate slug on one ATS turned out to be."""

    source: str
    slug: str
    status: BoardStatus
    n_jobs: int = 0
    has_eu: bool = False
    has_remote: bool = False

    @property
    def is_usable(self) -> bool:
        return self.status is BoardStatus.ACTIVE

    def as_seed_entry(self, name: str | None = None, added: str | None = None) -> dict:
        entry = {
            "ats": self.source,
            "slug": self.slug,
            "name": name or self.slug,
            "status": self.status.value,
            "n_jobs": self.n_jobs,
            "has_eu": self.has_eu,
            "has_remote": self.has_remote,
        }
        if added:
            entry["added"] = added
        return entry


def classify_payload(source: str, slug: str, payload) -> Probe:
    """Read a board's answer without fetching it, so the rules are testable.

    The EU and remote flags are sampled from the postings themselves using the
    same region rules the pipeline uses. The recon script had its own copy of a
    European city list, which is exactly how the seed's idea of "has EU" drifted
    from the dashboard's.
    """
    if payload is None:
        return Probe(source, slug, BoardStatus.DEAD)
    parse = PARSERS.get(source)
    if parse is None:
        return Probe(source, slug, BoardStatus.DEAD)
    try:
        jobs = parse(payload, slug)
    except (AttributeError, TypeError, KeyError):
        # A board answering 200 with something that is not its documented shape.
        return Probe(source, slug, BoardStatus.DEAD)
    if not jobs:
        return Probe(source, slug, BoardStatus.EMPTY)
    return Probe(
        source=source,
        slug=slug,
        status=BoardStatus.ACTIVE,
        n_jobs=len(jobs),
        has_eu=any(detect_region(job.get("location_raw")).region is Region.EU for job in jobs),
        has_remote=any(job.get("is_remote") for job in jobs),
    )


def probe_board(client, source: str, slug: str, sleeper=None) -> Probe:
    """Ask one ATS whether it hosts this slug."""
    if source not in SOURCES:
        return Probe(source, slug, BoardStatus.DEAD)
    from etl.config import SOURCES as ENDPOINTS

    try:
        payload = get_json(client, ENDPOINTS[source].format(slug=slug), sleeper)
    except Exception:  # noqa: BLE001 - a candidate that errors is simply not a board
        return Probe(source, slug, BoardStatus.DEAD)
    return classify_payload(source, slug, payload)


def dedupe_candidates(probes: list[Probe]) -> list[Probe]:
    """One entry per company, preferring the board that actually has postings.

    A company mid-migration answers on two ATSs, usually with the old one empty.
    Seeding both means crawling a dead board every day forever; seeding the
    wrong one means missing the company entirely.
    """
    best: dict[str, Probe] = {}
    for probe in probes:
        current = best.get(probe.slug)
        if current is None:
            best[probe.slug] = probe
            continue
        # active beats empty beats dead; then more postings wins
        rank = lambda p: (p.status is not BoardStatus.ACTIVE, p.status is BoardStatus.DEAD, -p.n_jobs)  # noqa: E731
        if rank(probe) < rank(current):
            best[probe.slug] = probe
    return [best[slug] for slug in sorted(best)]
