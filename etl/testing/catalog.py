"""A scripted skill labeller, standing in for Gemini.

No test may call the model: it needs a key, it costs money, and it is not
deterministic. What the pipeline actually depends on is far narrower than "an
LLM" — it needs something that takes a batch of postings and returns a mapping
of id to skills, and that sometimes misbehaves in the four ways that have
happened in production.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["ScriptedLabeller", "keyword_labeller", "QuotaExhausted"]


class QuotaExhausted(RuntimeError):
    """What the free tier raises once the daily budget is gone.

    The message matters: the caller recognises quota exhaustion by matching the
    text, and stopping for the day rather than burning retries depends on it.
    """

    def __init__(self, message: str = "RESOURCE_EXHAUSTED: quota exceeded (429)") -> None:
        super().__init__(message)


@dataclass
class ScriptedLabeller:
    """Answers each batch from a script, and records what it was asked.

    ``answers`` maps a posting's text fragment to the skills to return for it.
    ``failures`` is a list of exceptions to raise on the first calls — that is
    how the three-consecutive-failures rule and the quota stop get exercised.
    ``omit`` names fragments the model should silently drop from its reply,
    which is the misbehaviour that used to poison the cache with null rows.
    """

    answers: dict[str, list[str]] = field(default_factory=dict)
    failures: list[Exception] = field(default_factory=list)
    omit: set[str] = field(default_factory=set)
    calls: list[list[dict]] = field(default_factory=list)

    def __call__(self, batch: list[dict]) -> dict:
        self.calls.append(batch)
        if self.failures:
            raise self.failures.pop(0)
        items = []
        for posting in batch:
            haystack = f"{posting.get('title', '')} {posting.get('text', '')}"
            if any(fragment in haystack for fragment in self.omit):
                continue
            skills: list[str] = []
            for fragment, labels in self.answers.items():
                if fragment in haystack:
                    skills = labels
                    break
            items.append({"id": posting["id"], "skills": skills})
        return {"items": items}

    @property
    def batch_sizes(self) -> list[int]:
        return [len(batch) for batch in self.calls]

    @property
    def labelled(self) -> int:
        return sum(len(batch) for batch in self.calls)


def keyword_labeller(**mapping: list[str]) -> ScriptedLabeller:
    """``keyword_labeller(Python=["Python"], backend=["Go", "SQL"])``."""
    return ScriptedLabeller(answers=dict(mapping))
