"""Build a 25-example eval draft (real JDs + LLM draft labels) for owner review (PLAN.md §6.4)."""
import json
import pathlib
import random
from collections import Counter

from etl.config import LLM_TEXT_TRIM
from etl.fetch import make_client
from etl.normalize import passes_role_filter, seniority_of
from etl.skills import extract_llm
from etl.sources import fetch_ashby, fetch_greenhouse, fetch_lever

random.seed(42)
c = make_client()
sources = [(fetch_greenhouse, "gitlab"), (fetch_greenhouse, "cloudflare"), (fetch_ashby, "ramp"),
           (fetch_ashby, "openai"), (fetch_lever, "palantir"), (fetch_greenhouse, "figma")]
pool = []
for fn, slug in sources:
    for j in fn(c, slug):
        if passes_role_filter(j["title"], j.get("department")) and len(j.get("description") or "") > 400:
            pool.append(j)
random.shuffle(pool)

picks = []
for j in pool:
    if len([p for p in picks if p["source"] == j["source"]]) >= 9:
        continue
    picks.append(j)
    if len(picks) >= 25:
        break

batch = [{"id": i, "title": p["title"], "text": (p["description"] or "")[:LLM_TEXT_TRIM]}
         for i, p in enumerate(picks)]
labels = extract_llm(batch)

rows = [{"id": i, "title": p["title"], "text": (p["description"] or "")[:LLM_TEXT_TRIM],
         "expected": labels.get(i, [])} for i, p in enumerate(picks)]
pathlib.Path("data/eval").mkdir(parents=True, exist_ok=True)
with open("data/eval/skills_eval.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"wrote {len(rows)} eval examples | by source: {dict(Counter(p['source'] for p in picks))}")
print("\n=== DRAFT labels (owner must verify per §6.4) ===")
for r in rows:
    print(f"  [{r['id']:2}] {r['title'][:46]:46} -> {r['expected']}")
