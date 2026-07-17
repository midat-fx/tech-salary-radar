import sys, json, re
sys.path.insert(0, "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh")
from hhlib import get, jload

SCRATCH = "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh"
d = json.load(open(f"{SCRATCH}/kz_python.json"))
items = d["items"]
pick = next((i for i in items if i.get("salary")), items[0])
vid = pick["id"]
print(f"picked id={vid} name={pick['name']!r} salary={pick.get('salary')}")

st, hd, body, url = get(f"/vacancies/{vid}")
print(f"\n[detail] HTTP {st}  URL: {url}")
det = jload(body)
open(f"{SCRATCH}/detail.json", "w").write(body)
if st == 200:
    print("  keys:", sorted(det.keys()))
    print("  key_skills:", json.dumps(det.get("key_skills"), ensure_ascii=False))
    desc = det.get("description") or ""
    print(f"  description: len={len(desc)} is_html={'<' in desc}")
    print("  description[:400]:", desc[:400].replace(chr(10), " "))
    for k in ["salary", "salary_range", "experience", "schedule", "employment", "employment_form", "work_format", "professional_roles", "published_at", "area", "employer", "archived"]:
        print(f"  {k}: {json.dumps(det.get(k), ensure_ascii=False)[:300]}")
else:
    print("  body:", body[:600])
