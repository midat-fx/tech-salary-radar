"""Live Gemini eval: micro-F1 over data/eval/skills_eval.jsonl must be >= 0.75 (PLAN.md §6.4).

Marked llm_eval -> auto-skipped when GEMINI_API_KEY is absent (see conftest.py).
Batches exactly like production (LLM_BATCH_SIZE) so the score reflects the real pipeline, not a
single oversized call. Writes site/data/eval_badge.json for the README shields endpoint.
"""

import json
import os
import random
from pathlib import Path

import pytest

from etl.config import LLM_BATCH_SIZE
from etl.skills import extract_llm

EVAL = Path(__file__).parents[1] / "data" / "eval" / "skills_eval.jsonl"
BADGE = Path(__file__).parents[1] / "site" / "data" / "eval_badge.json"
THRESHOLD = 0.75


def _f1(counts):
    tp, fp, fn = counts
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0


def _bootstrap(per_doc, replicates=1000, seed=11):
    """Document-level bootstrap CI for micro-F1 (which examples you sampled matters)."""
    rng = random.Random(seed)
    scores = []
    for _ in range(replicates):
        sample = rng.choices(per_doc, k=len(per_doc))
        scores.append(_f1(tuple(sum(c[i] for c in sample) for i in range(3))))
    scores.sort()
    return scores[int(0.025 * (len(scores) - 1))], scores[int(0.975 * (len(scores) - 1))]


@pytest.mark.llm_eval
def test_skills_micro_f1():
    if not EVAL.exists():
        pytest.skip("eval set not built yet (needs owner-reviewed labels)")
    examples = [json.loads(line) for line in EVAL.read_text().splitlines() if line.strip()]

    got = {}
    for start in range(0, len(examples), LLM_BATCH_SIZE):
        chunk = examples[start:start + LLM_BATCH_SIZE]
        batch = [{"id": n, "title": e["title"], "text": e["text"]} for n, e in enumerate(chunk)]
        result = extract_llm(batch)                       # real Gemini, production batch size
        for n, e in enumerate(chunk):
            got[e["id"]] = result.get(n, [])

    per_doc, diffs = [], []
    for e in examples:
        pred, exp = set(got.get(e["id"], [])), set(e["expected"])
        counts = (len(pred & exp), len(pred - exp), len(exp - pred))
        per_doc.append(counts)
        if pred != exp:
            diffs.append(f"  id={e['id']} {e['title'][:44]}: "
                         f"+{sorted(pred - exp) or '-'} -{sorted(exp - pred) or '-'}")
    f1 = _f1(tuple(sum(c[i] for c in per_doc) for i in range(3)))
    lo, hi = _bootstrap(per_doc)
    print(f"\nmicro-F1 = {f1:.3f}  (95% CI [{lo:.3f}, {hi:.3f}], n={len(examples)} examples)")
    if diffs:
        print("per-example differences:\n" + "\n".join(diffs))

    if os.environ.get("WRITE_EVAL_BADGE"):
        BADGE.parent.mkdir(parents=True, exist_ok=True)
        BADGE.write_text(json.dumps({
            "schemaVersion": 1, "label": "skills eval F1", "message": f"{f1:.2f}",
            "color": "brightgreen" if f1 >= THRESHOLD else "red"}))

    assert f1 >= THRESHOLD, f"micro-F1={f1:.3f} < {THRESHOLD}\n" + "\n".join(diffs)
