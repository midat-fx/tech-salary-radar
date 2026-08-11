"""Write a published file so that an unchanged day produces an unchanged file.

The site's JSON is committed to git by the same cron job that writes the
parquet. If serialisation is not canonical, every run produces a diff whether or
not anything changed — and then the commit history stops being evidence that
something happened, which is the property the whole daily rhythm is for.

Canonical here means: no incidental whitespace, non-ASCII kept as itself so the
Russian copy is readable in a diff, and keys in the order the builder produced
rather than sorted. Sorting would be tidier and would also make an accidental
reordering upstream invisible.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["SEPARATORS", "dumps", "write_json", "would_change"]

#: No space after the comma or the colon: this file is downloaded by a browser
#: on every page view, and the whitespace is a measurable share of it.
SEPARATORS = (",", ":")


def dumps(payload) -> str:
    """The exact bytes a published file contains."""
    return json.dumps(payload, ensure_ascii=False, separators=SEPARATORS)


def would_change(path: str | Path, payload) -> bool:
    """True when writing this payload would produce a different file.

    Used by the run report rather than to skip the write: knowing that an
    aggregation produced identical output is a signal worth printing, and
    skipping the write would hide a file somebody deleted by hand.
    """
    target = Path(path)
    if not target.exists():
        return True
    return target.read_text() != dumps(payload)


def write_json(directory: str | Path, name: str, payload) -> Path:
    """Write one published file, creating the directory if it is not there."""
    out = Path(directory) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(payload))
    return out
