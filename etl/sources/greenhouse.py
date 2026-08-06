"""Greenhouse: the board with the most jobs and the least structure.

Greenhouse has no compensation field at all. US pay-transparency law pushed the
range into the description, which is why this is the only adapter whose output
sends the whole ad downstream and why :mod:`etl.money.parse` exists.

It is also the only board that sends HTML, and the only one whose remote signal
is the location string.
"""

from __future__ import annotations

from etl.config import SOURCES
from etl.geo import is_remote_text
from etl.sources.html import strip_html
from etl.sources.transport import get_json

__all__ = ["fetch", "parse", "URL"]

URL = SOURCES["greenhouse"]


def parse(payload, slug: str) -> list[dict]:
    """Board payload -> raw job dicts. An absent or empty board yields nothing."""
    if not payload:
        return []
    jobs = []
    for job in payload.get("jobs", []):
        location = (job.get("location") or {}).get("name") or ""
        departments = job.get("departments") or []
        jobs.append(
            {
                "source": "greenhouse",
                "company": slug,
                "job_id": str(job.get("id")),
                "title": job.get("title") or "",
                "location_raw": location,
                "is_remote": is_remote_text(location),
                "employment_type": None,
                # first_published is when the job went up; updated_at moves every
                # time a recruiter touches it, and would make every edited job
                # look new.
                "published_at": job.get("first_published") or job.get("updated_at"),
                "apply_url": job.get("absolute_url"),
                "department": (departments[0].get("name") if departments else None),
                "description": strip_html(job.get("content")),
                "raw_compensation": None,
            }
        )
    return jobs


def fetch(client, slug: str, sleeper=None) -> list[dict]:
    return parse(get_json(client, URL.format(slug=slug), sleeper), slug)
