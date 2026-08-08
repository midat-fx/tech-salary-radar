"""What has already been labelled, and by which generation of the prompt.

The cache is the skills parquet itself — there is no second store. Reading it
answers the only two questions the extractor asks: which postings can be
skipped, and which carry labels from an older prompt and are worth redoing when
there is budget left.

The append-only shape is why a null row means something. A posting the model
processed and found no skills in gets one row with a null skill; a posting it
never saw gets no row at all. Collapsing those two into "no skills" is the
mistake ADR 0003 exists to prevent, and it deflated every premium on the site
until it was found.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from etl.config import PROMPT_VERSION

__all__ = ["CacheState", "read_cache_state", "processed_uids", "skills_glob"]


def skills_glob(data_dir: str | Path) -> Path:
    return Path(data_dir) / "skills"


@dataclass(frozen=True)
class CacheState:
    """Which postings are done, and which are done but out of date."""

    current: frozenset[str]
    stale: frozenset[str]

    @property
    def processed(self) -> frozenset[str]:
        """Everything with any label at all — the anti-join the extractor uses."""
        return self.current | self.stale

    def describe(self) -> str:
        return f"cache: {len(self.current)} current, {len(self.stale)} stale labels"


def _has_parquet(data_dir: str | Path) -> bool:
    return any(skills_glob(data_dir).rglob("*.parquet"))


def read_cache_state(data_dir: str | Path, prompt_version: str = PROMPT_VERSION) -> CacheState:
    """Split the cache into current and stale by the prompt that produced it.

    A posting labelled by several generations counts as current if *any* of its
    labels is current — the aggregator already resolves which generation wins,
    and re-extracting a posting that has a current label would spend budget to
    produce a row that changes nothing.
    """
    if not _has_parquet(data_dir):
        return CacheState(frozenset(), frozenset())
    import duckdb

    rows = duckdb.sql(
        f"SELECT job_uid, max(prompt_version) FROM "
        f"read_parquet('{skills_glob(data_dir)}/*/part.parquet') GROUP BY 1"
    ).fetchall()
    current = {uid for uid, version in rows if version == prompt_version}
    stale = {uid for uid, version in rows if version != prompt_version}
    return CacheState(frozenset(current), frozenset(stale))


def processed_uids(data_dir: str | Path) -> set[str]:
    """Every posting with any label. Empty when the cache does not exist yet."""
    if not _has_parquet(data_dir):
        return set()
    import duckdb

    return {
        row[0]
        for row in duckdb.sql(
            f"SELECT DISTINCT job_uid FROM read_parquet('{skills_glob(data_dir)}/*/part.parquet')"
        ).fetchall()
    }
