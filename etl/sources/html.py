"""Turn a board's HTML description into the plain text everything downstream reads.

Only Greenhouse sends HTML; Lever and Ashby have a ``descriptionPlain`` field.
But the salary parser and the LLM both see whatever comes out of here, so a
sloppy strip is not cosmetic: a tag boundary swallowed into a number turns
``$150,000</b> - <b>$180,000`` into something the range pattern cannot match,
and the posting silently loses its salary.
"""

from __future__ import annotations

import html
import re

__all__ = ["strip_html", "collapse_whitespace", "BLOCK_TAGS"]

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

#: Tags that end a line of prose. Replaced with a space rather than removed, so
#: "</li><li>" does not weld the last word of one bullet to the first of the next.
BLOCK_TAGS = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr|td|table|section)\b[^>]*>", re.I)


def collapse_whitespace(text: str) -> str:
    """Every run of whitespace becomes one space; the result is stripped."""
    return _WS.sub(" ", text).strip()


def strip_html(text: str | None) -> str:
    """Unescape entities, drop tags, collapse whitespace.

    Entities are unescaped **before** tags are dropped, which means an escaped
    ``&lt;script&gt;`` written deliberately in the prose is removed along with
    the real markup. That is the accepted side of the trade: the alternative
    order leaves genuine double-escaped markup in the text that the LLM then
    reads as content, and losing the literal word costs nothing downstream.
    """
    if not text:
        return ""
    unescaped = html.unescape(text)
    spaced = BLOCK_TAGS.sub(" ", unescaped)
    return collapse_whitespace(_TAG.sub(" ", spaced))
