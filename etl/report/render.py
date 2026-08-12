"""Turn a run's numbers into the fixed-order text the report promises.

Formatting rules, all chosen so two runs over the same data produce identical
bytes:

* an absent value prints as ``-`` rather than being skipped, so the line count
  is the same whether or not a stage ran;
* shares print to one decimal place, because a share that wobbles in the fourth
  makes a diff of two runs unreadable;
* lists print sorted and comma-joined, because dict iteration order is not
  something to publish.
"""

from __future__ import annotations

from etl.report.fields import SECTIONS, Field

__all__ = ["render", "render_line", "format_value", "MISSING"]

MISSING = "-"


def format_value(field: Field, value) -> str:
    """One value, in the form its kind declares."""
    if value is None:
        return MISSING
    if field.kind == "share":
        return f"{float(value) * 100:.1f}%"
    if field.kind == "list":
        if not value:
            return MISSING
        if isinstance(value, dict):
            return ", ".join(f"{k}={v}" for k, v in sorted(value.items()))
        return ", ".join(sorted(str(item) for item in value))
    if field.kind == "text":
        text = str(value).strip()
        return text or MISSING
    return str(value)


def render_line(field: Field, value) -> str:
    """``postings fetched: 6546``. The label is padded so the values line up."""
    return f"  {field.label + ':':<28}{format_value(field, value)}"


def render(values: dict, title: str | None = None) -> str:
    """The whole report. Sections in declared order, blank line between them."""
    blocks: list[str] = []
    if title:
        blocks.append(title)
    for section, fields in SECTIONS.items():
        lines = [f"{section}:"]
        lines.extend(render_line(field, values.get(field.key)) for field in fields)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
