"""Deterministic linter for the eval set — no LLM involved (PLAN improvements 1.8).

The eval gate is only meaningful if its ground truth is real: every `expected` label must be
literally present in the posting text (canonical name or a catalogue alias). This catches
hallucinated labels permanently, which a model-scored gate never can.
"""

import json
import re
from pathlib import Path

import pytest

from etl.skills_catalog import SKILLS

EVAL = Path(__file__).parents[1] / "data" / "eval" / "skills_eval.jsonl"


def _examples():
    if not EVAL.exists():
        return []
    return [json.loads(line) for line in EVAL.read_text().splitlines() if line.strip()]


def mentions(skill, text):
    """True if the canonical name or any alias occurs literally (word-boundary, case-insensitive)."""
    variants = [skill] + list(SKILLS.get(skill, []))
    for v in variants:
        # '.NET', 'C++', 'CI/CD' contain regex metacharacters; \b is wrong next to punctuation
        pattern = re.escape(v)
        left = r"\b" if v[:1].isalnum() else ""
        right = r"\b" if v[-1:].isalnum() else ""
        if re.search(left + pattern + right, text, re.I):
            return True
    return False


@pytest.mark.skipif(not EVAL.exists(), reason="eval set not built yet")
def test_every_expected_label_is_literally_mentioned():
    problems = []
    for ex in _examples():
        haystack = f"{ex['title']}\n{ex['text']}"
        for skill in ex["expected"]:
            if not mentions(skill, haystack):
                problems.append(f"id={ex['id']} '{ex['title'][:40]}': '{skill}' never appears")
    assert not problems, "phantom labels in the eval set:\n" + "\n".join(problems)


@pytest.mark.skipif(not EVAL.exists(), reason="eval set not built yet")
def test_eval_set_shape():
    ex = _examples()
    assert len(ex) >= 25, f"eval set too small: {len(ex)}"
    assert len({e["id"] for e in ex}) == len(ex), "duplicate ids"
    assert all(e["text"].strip() for e in ex), "empty text in eval set"
    # every catalogue label used must be a real canonical skill
    unknown = {s for e in ex for s in e["expected"] if s not in SKILLS}
    assert not unknown, f"labels outside the catalogue: {unknown}"
