"""Live Gemini eval: micro-F1 over data/eval/skills_eval.jsonl must be >= 0.75 (PLAN.md §6.4).

Marked llm_eval -> auto-skipped when GEMINI_API_KEY is absent (see conftest.py).
Also skipped until the owner-reviewed eval set exists.
"""

import json
from pathlib import Path

import pytest

from etl.skills import extract_llm

EVAL = Path(__file__).parents[1] / "data" / "eval" / "skills_eval.jsonl"


@pytest.mark.llm_eval
def test_skills_micro_f1():
    if not EVAL.exists():
        pytest.skip("eval set not built yet (needs owner-reviewed labels)")
    examples = [json.loads(line) for line in EVAL.read_text().splitlines() if line.strip()]
    batch = [{"id": i, "title": e["title"], "text": e["text"]} for i, e in enumerate(examples)]
    got = extract_llm(batch)  # real Gemini

    tp = fp = fn = 0
    diffs = []
    for i, e in enumerate(examples):
        pred, exp = set(got.get(i, [])), set(e["expected"])
        tp += len(pred & exp)
        fp += len(pred - exp)
        fn += len(exp - pred)
        if pred != exp:
            diffs.append(f"{e['title'][:40]}: +{sorted(pred - exp)} -{sorted(exp - pred)}")
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    assert f1 >= 0.75, f"micro-F1={f1:.3f} < 0.75\n" + "\n".join(diffs)
