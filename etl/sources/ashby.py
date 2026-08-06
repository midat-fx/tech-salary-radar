"""Ashby: the only board with structured compensation, and the only one with tiers.

A posting can carry several compensation tiers — different locations, different
levels — occasionally in different currencies. Picking one is a decision with
consequences for the published median, so it lives in :mod:`etl.salary` where it
can be tested; this adapter hands over the whole structure untouched.
"""

from __future__ import annotations

from etl.config import SOURCES
from etl.sources.transport import get_json

__all__ = ["fetch", "parse", "URL"]

URL = SOURCES["ashby"]


def parse(payload, slug: str) -> list[dict]:
    """Board payload -> raw job dicts."""
    if not payload:
        return []
    return [
        {
            "source": "ashby",
            "company": slug,
            "job_id": str(job.get("id")),
            "title": job.get("title") or "",
            "location_raw": job.get("location") or "",
            "is_remote": bool(job.get("isRemote")),
            "employment_type": job.get("employmentType"),
            "published_at": job.get("publishedAt"),
            "apply_url": job.get("jobUrl"),
            "department": job.get("department"),
            "description": job.get("descriptionPlain") or "",
            "raw_compensation": job.get("compensation"),
        }
        for job in payload.get("jobs", [])
    ]


def fetch(client, slug: str, sleeper=None) -> list[dict]:
    return parse(get_json(client, URL.format(slug=slug), sleeper), slug)
