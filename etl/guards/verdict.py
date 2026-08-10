"""What a guard answers, and how several answers combine.

Every guard in this package returns the same shape, because the pipeline treats
them the same way: any refusal stops the day, and the reasons are printed
together rather than one at a time. A guard that raised instead would hide the
other guards' findings behind whichever ran first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = ["Severity", "Finding", "Verdict", "passed", "refuse"]


class Severity(str, Enum):
    WARN = "warn"
    """Worth printing and watching; the day is still written."""

    REFUSE = "refuse"
    """The day would poison an append-only history. Nothing is written."""


@dataclass(frozen=True)
class Finding:
    """One thing a guard noticed, in a sentence an operator can act on."""

    guard: str
    severity: Severity
    detail: str

    def __str__(self) -> str:
        return f"[{self.severity.value}] {self.guard}: {self.detail}"


@dataclass
class Verdict:
    """Everything the guards noticed about one day."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def refusals(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.REFUSE]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARN]

    @property
    def ok(self) -> bool:
        return not self.refusals

    def add(self, guard: str, severity: Severity, detail: str) -> "Verdict":
        self.findings.append(Finding(guard, severity, detail))
        return self

    def merge(self, other: "Verdict") -> "Verdict":
        self.findings.extend(other.findings)
        return self

    def describe(self) -> str:
        if not self.findings:
            return "guards: clear"
        return "; ".join(str(f) for f in self.findings)


def passed(guard: str) -> Verdict:
    """A guard that found nothing. Named rather than an empty literal so a
    caller reads the intent instead of counting brackets."""
    return Verdict()


def refuse(guard: str, detail: str) -> Verdict:
    return Verdict().add(guard, Severity.REFUSE, detail)
