"""Shields.io endpoints — the two numbers that appear in the README.

A badge is a tiny JSON file in a fixed schema. It is here rather than inline in
the aggregator because the README is a public surface: a badge that stops
updating, or that says ``0``, is the most visible possible failure and the
easiest to produce by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Badge", "jobs_badge", "eval_badge", "GREEN", "AMBER", "RED"]

GREEN = "brightgreen"
AMBER = "orange"
RED = "red"


@dataclass(frozen=True)
class Badge:
    """The shields endpoint schema, version 1."""

    label: str
    message: str
    color: str

    def as_dict(self) -> dict:
        return {
            "schemaVersion": 1,
            "label": self.label,
            "message": self.message,
            "color": self.color,
        }


def _thousands(value: int) -> str:
    """``6546`` -> ``"6 546"``. A thin space reads better than a comma in the
    Russian dashboard and does not need escaping in a URL."""
    return f"{value:,}".replace(",", " ")


def jobs_badge(active: int) -> Badge:
    """How many postings the last snapshot held.

    Zero is red rather than green: a badge saying "0 jobs tracked" in green is
    the pipeline reporting its own failure as a success.
    """
    if active <= 0:
        return Badge("jobs tracked", "none", RED)
    return Badge("jobs tracked", _thousands(active), GREEN)


def eval_badge(f1: float | None, threshold: float = 0.75) -> Badge:
    """The label quality score, coloured against the threshold CI enforces."""
    if f1 is None:
        return Badge("skill eval", "not run", AMBER)
    color = GREEN if f1 >= threshold else RED
    return Badge("skill eval", f"F1 {f1:.2f}", color)
