"""Gather a run's numbers from the pieces that produced them.

Each stage reports its own statistics in its own shape — a dataclass, a dict,
a guard verdict — and this is the one place that knows how to read all of them.
Keeping it here rather than in the pipeline means a stage can change what it
counts without the report's field list moving, and means the report can be
built from recorded pieces in a test.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["RunReport", "collect"]


@dataclass
class RunReport:
    """A run's numbers, plus the text form and the machine form of them."""

    values: dict = field(default_factory=dict)
    title: str = ""

    def text(self) -> str:
        from etl.report.render import render

        return render(self.values, self.title or None)

    def as_dict(self) -> dict:
        """What lands in ``data/cache/last_run.json``.

        Deliberately the raw values rather than the rendered text: the file is
        read back by the aggregator to publish coverage, and re-parsing prose
        would be an odd way to move a number between two parts of one program.
        """
        return dict(self.values)

    def __getitem__(self, key):
        return self.values[key]


def collect(
    *,
    day: str,
    seed_size: int,
    raw_jobs: int,
    snapshot_rows: int,
    new_rows: int,
    with_salary: int,
    filtered_non_tech: int = 0,
    skill_rows: int = 0,
    breaker=None,
    dedupe=None,
    guards=None,
    pay_stats: dict | None = None,
    llm_stats=None,
) -> RunReport:
    """Assemble the report from whatever the run produced."""
    pay_stats = pay_stats or {}
    refusals = {
        name.removeprefix("pay_"): count
        for name, count in pay_stats.items()
        if name.startswith("pay_") and count and name not in ("pay_accepted", "pay_empty")
    }
    values = {
        "boards": seed_size,
        "boards_reached": sum(st.successes for st in breaker.states.values()) if breaker else None,
        "raw_jobs": raw_jobs,
        "breaker": breaker.describe() if breaker else None,
        "filtered_non_tech": filtered_non_tech,
        "duplicates_removed": dedupe.duplicates_removed if dedupe else None,
        "snapshot_rows": snapshot_rows,
        "new_rows": new_rows,
        "with_salary": with_salary,
        "salary_share": (with_salary / snapshot_rows) if snapshot_rows else None,
        "pay_rejected": sum(refusals.values()) if refusals else 0,
        "pay_reasons": refusals,
        "skill_rows": skill_rows,
        "llm_extracted": getattr(llm_stats, "extracted", None),
        "llm_queue_depth": getattr(llm_stats, "queue_depth", None),
        "llm_missing_ids": getattr(llm_stats, "missing_ids", None),
        "guard_verdict": ("refused" if guards and not guards.ok else "clear") if guards else None,
        "guard_findings": [str(f) for f in guards.findings] if guards else [],
    }
    return RunReport(values=values, title=f"=== run {day} ===")
