"""Extend data/eval/skills_eval.jsonl with more Ashby AI-lab postings (PLAN improvements 1.8 step 4).

LLM proposes labels, then the deterministic literal-mention linter strips anything hallucinated,
so the ground truth stays grounded in the text. Owner review still applies (§6.4).
"""
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from etl.config import LLM_TEXT_TRIM  # noqa: E402
from etl.fetch import make_client  # noqa: E402
from etl.normalize import passes_role_filter, seniority_of  # noqa: E402
from etl.skills import extract_llm  # noqa: E402
from etl.sources import fetch_ashby  # noqa: E402
from tests.test_eval_labels import mentions  # noqa: E402

TARGET_TOTAL = 40
COMPANIES = ["harvey", "elevenlabs", "cursor", "abridge", "watershed", "baseten", "mercor"]

path = pathlib.Path("data/eval/skills_eval.jsonl")
existing = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
have_titles = {e["title"] for e in existing}
need = TARGET_TOTAL - len(existing)
print(f"have {len(existing)} examples, need {need} more")

random.seed(7)
client = make_client()
pool = []
for slug in COMPANIES:
    try:
        for j in fetch_ashby(client, slug):
            if (passes_role_filter(j["title"], j.get("department"))
                    and len(j.get("description") or "") > 600
                    and j["title"] not in have_titles):
                pool.append(j)
    except Exception as exc:
        print(f"  {slug}: {exc}")
random.shuffle(pool)

picks, seen_titles = [], set()
for j in pool:
    if j["title"] in seen_titles:
        continue
    seen_titles.add(j["title"])
    picks.append(j)
    if len(picks) >= need:
        break
print(f"picked {len(picks)} new postings; seniority mix: "
      f"{ {s: sum(1 for p in picks if seniority_of(p['title']) == s) for s in {seniority_of(p['title']) for p in picks}} }")

next_id = max(e["id"] for e in existing) + 1
rows = []
for i in range(0, len(picks), 10):
    chunk = picks[i:i + 10]
    batch = [{"id": n, "title": p["title"], "text": (p["description"] or "")[:LLM_TEXT_TRIM]}
             for n, p in enumerate(chunk)]
    labels = extract_llm(batch)
    for n, p in enumerate(chunk):
        text = (p["description"] or "")[:LLM_TEXT_TRIM]
        hay = f"{p['title']}\n{text}"
        # keep only labels that are literally present — the linter is the arbiter, not the model
        grounded = sorted({s for s in labels.get(n, []) if mentions(s, hay)})
        dropped = sorted(set(labels.get(n, [])) - set(grounded))
        if dropped:
            print(f"  id={next_id} dropped hallucinated: {dropped}")
        rows.append({"id": next_id, "title": p["title"], "text": text, "expected": grounded})
        next_id += 1

with path.open("a") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"appended {len(rows)} examples -> total {len(existing) + len(rows)}")
