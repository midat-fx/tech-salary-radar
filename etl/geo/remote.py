"""Whether a posting is remote, and what to do when the board contradicts itself.

Each ATS answers this differently: Ashby has an ``isRemote`` boolean, Lever a
``workplaceType`` enum, Greenhouse nothing at all — its location string is the
only evidence. So the three adapters produce a flag of very different quality,
and the location text has to be read as a second opinion regardless.

The contradiction is common and specific: a board flags a job remote while its
location says "San Francisco, CA (Hybrid)". Both facts are true — the role is
remote-eligible *within* a region — and collapsing them to one boolean loses the
one that matters for pay.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["RemoteReading", "read_remote", "is_remote_text", "HYBRID", "REMOTE_WORDS"]

REMOTE_WORDS = re.compile(r"\bremote\b|\bwork from home\b|\bwfh\b|\bdistributed\b|удал[её]нн", re.I)
HYBRID = re.compile(r"\bhybrid\b|\bon-?site\b|\bin[- ]office\b|\bin[- ]person\b", re.I)

#: "Remote (US)", "Remote - EMEA": remote, but anchored to a region. The anchor
#: is what decides which pay market the posting belongs to.
_ANCHORED = re.compile(r"remote[\s\-—(]*(us|usa|united states|eu|europe|emea|uk|apac|latam)", re.I)


@dataclass(frozen=True)
class RemoteReading:
    """The flag the board sent, what its location text says, and the verdict."""

    is_remote: bool
    #: The board said remote and the location also names a place or a hybrid
    #: arrangement. Not an error — remote-within-a-region — but worth counting.
    anchored: bool = False
    conflicting: bool = False

    @property
    def value(self) -> bool:
        return self.is_remote


def is_remote_text(location_raw: str | None) -> bool:
    """True when the location string itself says remote and does not say hybrid."""
    text = location_raw or ""
    if not REMOTE_WORDS.search(text):
        return False
    # "Remote or hybrid in Berlin" is not a remote posting for pay purposes.
    return not HYBRID.search(text) or bool(_ANCHORED.search(text))


def read_remote(flag: bool | None, location_raw: str | None) -> RemoteReading:
    """Combine a board's flag with its location text.

    The flag wins when it is set: a board that has the field knows better than a
    regex. When it is absent — Greenhouse — the text is all there is.
    """
    text = location_raw or ""
    from_text = is_remote_text(text)
    anchored = bool(_ANCHORED.search(text))
    if flag is None:
        return RemoteReading(from_text, anchored=anchored)
    if flag:
        conflicting = bool(HYBRID.search(text)) and not anchored
        return RemoteReading(True, anchored=anchored, conflicting=conflicting)
    # Flag says no, text says yes: trust the text only when it is unambiguous,
    # because a stale flag is more common than a location string that lies.
    return RemoteReading(from_text and not HYBRID.search(text), anchored=anchored,
                         conflicting=from_text)
