"""Reading and writing the hand-checked evaluation set.

The set is the only thing standing between a prompt change and a silent
regression in every premium on the site, and it is a JSONL file somebody edits
by hand. Both halves of that matter: it needs a loader that refuses malformed
lines loudly rather than skipping them, and a writer that produces a diff a
human can review.

Built once by a script under ``probe-scripts/`` that fetched live postings,
asked the model for draft labels, and wrote them out for review. That script
also had its own client, its own random seed and its own idea of the file
format. What is kept is the format and the rules; the fetching belongs to the
crawl and the labelling to :mod:`etl.skills.extract`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from etl.skills.quality import lint_labels

__all__ = ["EvalExample", "EvalSet", "read_evalset", "write_evalset", "DEFAULT_PATH"]

DEFAULT_PATH = Path("data/eval/skills_eval.jsonl")


@dataclass(frozen=True)
class EvalExample:
    """One posting and the labels a human decided are really in it."""

    id: str
    title: str
    text: str
    expected: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "expected": list(self.expected),
        }

    def as_posting(self, index: int) -> dict:
        """The shape the extractor consumes, so the set can be scored by the real path."""
        return {"id": index, "title": self.title, "text": self.text}


@dataclass(frozen=True)
class EvalSet:
    """The whole set, plus whatever the linter found wrong with it."""

    examples: tuple[EvalExample, ...]
    issues: tuple[str, ...] = ()

    def __len__(self) -> int:
        return len(self.examples)

    @property
    def is_clean(self) -> bool:
        return not self.issues

    @property
    def expected_by_id(self) -> dict[str, list[str]]:
        return {example.id: list(example.expected) for example in self.examples}

    def describe(self) -> str:
        return f"eval set: {len(self.examples)} examples, {len(self.issues)} issues"


def read_evalset(path: str | Path = DEFAULT_PATH) -> EvalSet:
    """Parse the JSONL file and lint it in one pass.

    A malformed line raises rather than being skipped. A set that silently
    shrinks is a set whose score means something different from last week's,
    and the score is compared against a threshold in CI.
    """
    lines = Path(path).read_text().splitlines()
    examples: list[EvalExample] = []
    raw: list[dict] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: not valid JSON — {exc}") from exc
        raw.append(item)
        examples.append(
            EvalExample(
                id=str(item.get("id", number)),
                title=item.get("title", ""),
                text=item.get("text", ""),
                expected=tuple(item.get("expected") or ()),
            )
        )
    issues = tuple(str(issue) for issue in lint_labels(raw))
    return EvalSet(tuple(examples), issues)


def write_evalset(examples: list[EvalExample], path: str | Path = DEFAULT_PATH) -> Path:
    """Write the set back, one example per line, keys in a fixed order.

    One line per example on purpose: a reviewer reads this in a pull request,
    and a pretty-printed array turns a one-label change into a twelve-line diff.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(example.as_dict(), ensure_ascii=False) for example in examples)
    out.write_text(body + "\n" if body else "")
    return out
