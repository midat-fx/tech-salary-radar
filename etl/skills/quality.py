"""Whether the labels are any good, measured against a hand-checked set.

The evaluation set is small — a few dozen postings labelled by hand — and it is
the only thing standing between a prompt change and a silent regression in every
premium on the site. A prompt that looks better in three examples and is worse
across the set is exactly what happened to ``v2``.

Two measures, because they fail in opposite directions:

* **Precision** — of the skills the model claimed, how many were really there.
  Low precision inflates a premium: postings land in the with-pool that do not
  belong there.
* **Recall** — of the skills really there, how many the model found. Low recall
  deflates it, and it deflates unevenly: rarer skills are missed more often.
"""

from __future__ import annotations

from dataclasses import dataclass

from etl.skills.catalog import CANONICAL, canonicalize

__all__ = ["LabelIssue", "lint_labels", "Score", "score_labels"]


@dataclass(frozen=True)
class LabelIssue:
    """Something wrong with the evaluation set itself, not with the model."""

    example_id: str
    problem: str

    def __str__(self) -> str:
        return f"{self.example_id}: {self.problem}"


def lint_labels(examples: list[dict]) -> list[LabelIssue]:
    """Check the hand-written evaluation set before trusting a score from it.

    A typo in an expected label is worse than a missing example: it makes the
    model look wrong forever on a skill it gets right, and the obvious response
    is to change the prompt.
    """
    issues: list[LabelIssue] = []
    seen: set[str] = set()
    for index, example in enumerate(examples):
        eid = str(example.get("id", index))
        if eid in seen:
            issues.append(LabelIssue(eid, "duplicate id"))
        seen.add(eid)
        if not (example.get("text") or "").strip():
            issues.append(LabelIssue(eid, "empty text"))
        expected = example.get("expected")
        if expected is None:
            issues.append(LabelIssue(eid, "no expected labels"))
            continue
        for label in expected:
            if label not in CANONICAL:
                suggestion = canonicalize(label)
                hint = f"; did you mean {suggestion!r}" if suggestion else ""
                issues.append(LabelIssue(eid, f"{label!r} is not a canonical skill{hint}"))
        if len(set(expected)) != len(expected):
            issues.append(LabelIssue(eid, "expected labels repeat"))
    return issues


@dataclass(frozen=True)
class Score:
    """Precision, recall and the counts they came from."""

    true_positive: int
    false_positive: int
    false_negative: int

    @property
    def precision(self) -> float:
        claimed = self.true_positive + self.false_positive
        return self.true_positive / claimed if claimed else 1.0

    @property
    def recall(self) -> float:
        present = self.true_positive + self.false_negative
        return self.true_positive / present if present else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def describe(self) -> str:
        return (
            f"precision {self.precision:.2f} recall {self.recall:.2f} f1 {self.f1:.2f} "
            f"(tp {self.true_positive} fp {self.false_positive} fn {self.false_negative})"
        )


def score_labels(expected: dict[str, list[str]], produced: dict[str, list[str]]) -> Score:
    """Compare produced labels with expected ones, per posting, then total.

    A posting the model dropped entirely counts every expected label as missed
    rather than being skipped — a model that answers nothing must not score
    perfectly on precision.
    """
    tp = fp = fn = 0
    for eid, want in expected.items():
        got = set(produced.get(eid, []))
        wanted = set(want)
        tp += len(wanted & got)
        fp += len(got - wanted)
        fn += len(wanted - got)
    return Score(tp, fp, fn)
