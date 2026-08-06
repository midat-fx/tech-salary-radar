"""Lever: a flat array of postings, with pay in a form-filled ``salaryRange``.

The range comes straight out of whatever the recruiter typed, so its bounds
arrive in either order and its currency is sometimes absent. Both are handled
in :mod:`etl.money`, not here — this adapter's job is to hand over what the
board said without interpreting it.
"""

from __future__ import annotations

from etl.clock import parse_iso
from etl.config import SOURCES
from etl.sources.transport import get_json

__all__ = ["fetch", "parse", "URL", "epoch_ms_to_iso"]

URL = SOURCES["lever"]


def epoch_ms_to_iso(milliseconds) -> str | None:
    """Lever timestamps are epoch milliseconds; everything else here is ISO-8601."""
    if milliseconds is None:
        return None
    try:
        seconds = float(milliseconds) / 1000
    except (TypeError, ValueError):
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def parse(payload, slug: str) -> list[dict]:
    """Board payload -> raw job dicts. ``None`` (404) and ``[]`` both yield nothing."""
    if not payload:
        return []
    jobs = []
    for job in payload:
        categories = job.get("categories") or {}
        workplace = (job.get("workplaceType") or "").lower()
        published = job.get("createdAt")
        jobs.append(
            {
                "source": "lever",
                "company": slug,
                "job_id": str(job.get("id")),
                "title": job.get("text") or "",
                "location_raw": categories.get("location") or "",
                "is_remote": workplace == "remote",
                "employment_type": categories.get("commitment"),
                "published_at": epoch_ms_to_iso(published)
                if isinstance(published, (int, float))
                else (parse_iso(published).isoformat() if parse_iso(published) else None),
                "apply_url": job.get("hostedUrl"),
                "department": categories.get("team"),
                "description": job.get("descriptionPlain") or "",
                "raw_compensation": job.get("salaryRange"),
            }
        )
    return jobs


def fetch(client, slug: str, sleeper=None) -> list[dict]:
    return parse(get_json(client, URL.format(slug=slug), sleeper), slug)
