"""The two job shapes: as a board sends it, and as the pipeline stores it.

The crawl produces one dict shape and the writer consumes another, and until
now the only description of either was a docstring in ``sources.py`` plus a
column tuple in ``normalize.py``. Neither was checked, so a board adding a
field, or a parser forgetting one, surfaced as a ``KeyError`` several stages
downstream — or worse, as a column of nulls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from etl.schema.errors import InvariantViolated

__all__ = [
    "RAW_JOB_FIELDS",
    "REQUIRED_RAW_FIELDS",
    "SENIORITIES",
    "REGIONS",
    "SOURCES",
    "RawJob",
    "job_uid",
    "split_uid",
    "check_raw_job",
]

#: Everything an adapter is expected to produce. A key outside this set is a
#: parser inventing a field; a required key missing is a parser that broke.
RAW_JOB_FIELDS = (
    "source",
    "company",
    "job_id",
    "title",
    "location_raw",
    "is_remote",
    "employment_type",
    "published_at",
    "apply_url",
    "department",
    "description",
    "raw_compensation",
)

#: Without these four a posting cannot be identified or filtered, so a row
#: missing any of them is dropped rather than stored with a hole.
REQUIRED_RAW_FIELDS = ("source", "company", "job_id", "title")

SOURCES = ("greenhouse", "lever", "ashby")
REGIONS = ("us", "eu", "other")

#: ``unspecified`` is a bucket, not a gap: ADR 0006 explains why ``L5`` and
#: ``IC3`` land there rather than being guessed into a level.
SENIORITIES = ("junior", "mid", "senior", "staff+", "unspecified")


@dataclass(frozen=True)
class RawJob:
    """A posting as an ATS adapter produced it, before any interpretation.

    Frozen because everything downstream derives new values from it rather than
    editing it, and an accidental mutation inside a generator pipeline is
    otherwise invisible.
    """

    source: str
    company: str
    job_id: str
    title: str
    location_raw: str = ""
    is_remote: bool = False
    employment_type: str | None = None
    published_at: str | None = None
    apply_url: str | None = None
    department: str | None = None
    description: str = ""
    raw_compensation: Any = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RawJob":
        """Build from an adapter's dict, refusing unknown keys.

        Unknown keys are refused rather than dropped: every one seen so far has
        been a typo or a half-finished rename, and dropping it produced a column
        that was quietly always null.
        """
        unknown = set(data) - set(RAW_JOB_FIELDS)
        if unknown:
            raise InvariantViolated("raw_job", f"unknown fields {sorted(unknown)}")
        check_raw_job(data)
        return cls(
            source=str(data["source"]),
            company=str(data["company"]),
            job_id=str(data["job_id"]),
            title=str(data["title"] or ""),
            location_raw=str(data.get("location_raw") or ""),
            is_remote=bool(data.get("is_remote")),
            employment_type=data.get("employment_type"),
            published_at=data.get("published_at"),
            apply_url=data.get("apply_url"),
            department=data.get("department"),
            description=str(data.get("description") or ""),
            raw_compensation=data.get("raw_compensation"),
        )

    def to_mapping(self) -> dict[str, Any]:
        """Back to the dict shape the existing pipeline stages consume."""
        return {name: getattr(self, name) for name in RAW_JOB_FIELDS}

    @property
    def uid(self) -> str:
        return job_uid(self.source, self.company, self.job_id)


def check_raw_job(data: Mapping[str, Any]) -> None:
    """Raise unless the mapping can be identified and attributed to a real source."""
    for name in REQUIRED_RAW_FIELDS:
        value = data.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise InvariantViolated("raw_job", f"required field {name!r} is empty")
    if data["source"] not in SOURCES:
        raise InvariantViolated("raw_job", f"unknown source {data['source']!r}")


def job_uid(source: str, company: str, job_id: str) -> str:
    """The stable identity of a posting: ``source:company:job_id``.

    Board slugs and job ids are opaque strings from three different vendors, so
    the separator has to survive whatever they contain. Colons do occur in
    Ashby ids, which is why :func:`split_uid` splits from the left with a bound
    rather than on every colon.
    """
    return f"{source}:{company}:{job_id}"


def split_uid(uid: str) -> tuple[str, str, str]:
    """Inverse of :func:`job_uid`. The id keeps any colons it contained."""
    parts = uid.split(":", 2)
    if len(parts) != 3:
        raise InvariantViolated("raw_job", f"job_uid {uid!r} is not source:company:job_id")
    return parts[0], parts[1], parts[2]
