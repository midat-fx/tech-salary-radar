"""The run report's field order, fixed once so the text can be compared exactly.

The report is the pipeline's only observable surface between "it exited zero"
and "read the parquet". That makes its *shape* a contract: a caller that greps
it, a CI step that diffs two runs, or a test that asserts on it all break when a
field moves, and none of them breaks loudly.

So the order lives here, as data, and the renderer walks it. Adding a field is
an edit in one place; reordering is a visible change to a list somebody has to
mean.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Field", "SECTIONS", "FIELD_ORDER", "field_names", "section_of"]


@dataclass(frozen=True)
class Field:
    """One line of the report: its key, its label, and how to render its value."""

    key: str
    label: str
    kind: str = "int"
    """``int``, ``share``, ``text`` or ``list``. Decides formatting only."""


#: Section -> fields, in the order they are printed. Sections are separated by a
#: blank line in the text form and are the only structure it has.
SECTIONS: dict[str, tuple[Field, ...]] = {
    "crawl": (
        Field("boards", "boards in seed"),
        Field("boards_reached", "boards answered"),
        Field("raw_jobs", "postings fetched"),
        Field("breaker", "circuit breaker", "text"),
    ),
    "filter": (
        Field("filtered_non_tech", "dropped as non-tech"),
        Field("duplicates_removed", "cross-board duplicates"),
        Field("snapshot_rows", "rows written"),
        Field("new_rows", "first seen today"),
    ),
    "pay": (
        Field("with_salary", "rows with a salary"),
        Field("salary_share", "salary coverage", "share"),
        Field("pay_rejected", "ranges found and refused"),
        Field("pay_reasons", "refusal reasons", "list"),
    ),
    "skills": (
        Field("skill_rows", "skill rows written"),
        Field("llm_extracted", "postings labelled"),
        Field("llm_queue_depth", "postings waiting"),
        Field("llm_missing_ids", "postings the model dropped"),
    ),
    "guards": (
        Field("guard_verdict", "verdict", "text"),
        Field("guard_findings", "findings", "list"),
    ),
}

FIELD_ORDER: tuple[Field, ...] = tuple(f for fields in SECTIONS.values() for f in fields)


def field_names() -> tuple[str, ...]:
    """Every key the report can print, in print order."""
    return tuple(f.key for f in FIELD_ORDER)


def section_of(key: str) -> str | None:
    for section, fields in SECTIONS.items():
        if any(f.key == key for f in fields):
            return section
    return None
