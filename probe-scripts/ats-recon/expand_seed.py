"""Expand data/seed_companies.json to >=300 active boards using public ATS company lists
(Feashliaa/job-board-aggregator), validated live. Appends only status=active entries.
"""
import json
import random
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

UA = "tech-salary-radar/1.0 (+https://github.com/midat-fx/tech-salary-radar; midat.faizov@gmail.com)"
ADDED = "2026-07-18"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "seed_companies.json"
TARGET_ACTIVE = 320
BUDGET = 1600

LISTS = {
    "greenhouse": "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/greenhouse_companies.json",
    "lever": "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/lever_companies.json",
    "ashby": "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/ashby_companies.json",
}
URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{s}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{s}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{s}?includeCompensation=true",
}
EU = ["united kingdom", "england", "london", "germany", "berlin", "munich", "france", "paris",
      "spain", "madrid", "barcelona", "netherlands", "amsterdam", "ireland", "dublin", "poland",
      "warsaw", "sweden", "stockholm", "portugal", "lisbon", "italy", "rome", "milan", "belgium",
      "brussels", "austria", "vienna", "denmark", "copenhagen", "finland", "helsinki", "norway",
      "oslo", "czech", "prague", "romania", "bucharest", "estonia", "tallinn", "lithuania",
      "latvia", "greece", "hungary", "budapest", "switzerland", "zurich", "luxembourg", "emea"]

PLAUSIBLE = re.compile(r"^[a-z][a-z0-9-]{2,30}$")


def plausible(slug):
    if not PLAUSIBLE.match(slug):
        return False
    if re.search(r"\d{4,}", slug):     # long digit runs = junk/ids
        return False
    letters = sum(c.isalpha() for c in slug)
    return letters >= max(3, int(0.5 * len(slug)))


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def parse(ats, body):
    try:
        d = json.loads(body)
    except Exception:
        return None, []
    if ats == "lever":
        jobs = d if isinstance(d, list) else []
        locs = [((j.get("categories") or {}).get("location") or "") + " " + (j.get("workplaceType") or "") for j in jobs[:25]]
    else:
        jobs = d.get("jobs", []) if isinstance(d, dict) else []
        if ats == "greenhouse":
            locs = [((j.get("location") or {}).get("name") or "") for j in jobs[:25]]
        else:
            locs = [((j.get("location") or "") + (" remote" if j.get("isRemote") else "")) for j in jobs[:25]]
    return len(jobs), [x.lower() for x in locs]


seed = json.loads(OUT.read_text())
known = {(r["ats"], r["slug"]) for r in seed}
active_now = sum(1 for r in seed if r["status"] == "active")
print(f"start: {len(seed)} entries, {active_now} active; target {TARGET_ACTIVE}")

candidates = []
for ats, url in LISTS.items():
    code, body = get(url)
    slugs = json.loads(body) if code == 200 else []
    fresh = [s for s in slugs if plausible(s) and (ats, s) not in known]
    random.shuffle(fresh)
    candidates += [(ats, s) for s in fresh]
    print(f"{ats}: {len(slugs)} listed, {len(fresh)} fresh plausible")
random.shuffle(candidates)

checked = 0
added = 0
for ats, slug in candidates:
    if active_now >= TARGET_ACTIVE or checked >= BUDGET:
        break
    checked += 1
    code, body = get(URLS[ats].format(s=slug))
    n, locs = parse(ats, body)
    if code == 200 and n and n > 0:
        seed.append({"name": slug, "ats": ats, "slug": slug, "status": "active", "added": ADDED,
                     "n_jobs": n, "has_eu": any(any(t in loc for t in EU) for loc in locs),
                     "has_remote": any("remote" in loc for loc in locs)})
        active_now += 1
        added += 1
        if added % 20 == 0:
            print(f"  +{added} active (total active {active_now}, checked {checked})")
    time.sleep(0.3)

# dedup by normalized name, prefer active
best = {}
for r in sorted(seed, key=lambda r: 0 if r["status"] == "active" else 1):
    best.setdefault(r["name"].lower(), r)
final = sorted(best.values(), key=lambda r: (r["ats"], r["slug"]))
OUT.write_text(json.dumps(final, ensure_ascii=False, indent=2))

active = [r for r in final if r["status"] == "active"]
from collections import Counter
print("\n==== EXPAND SUMMARY ====")
print(f"checked {checked}, added {added} active")
print(f"total entries {len(final)} | ACTIVE {len(active)}")
print(f"active by ats: {dict(Counter(r['ats'] for r in active))}")
print(f"active EU {sum(r.get('has_eu') for r in active)} ({100*sum(r.get('has_eu') for r in active)//max(1,len(active))}%) | remote {sum(r.get('has_remote') for r in active)} ({100*sum(r.get('has_remote') for r in active)//max(1,len(active))}%)")
print(f"total active jobs {sum(r.get('n_jobs',0) for r in active)}")
