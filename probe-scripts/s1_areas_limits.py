import sys, json
sys.path.insert(0, "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh")
from hhlib import get, jload

SCRATCH = "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh"

# --- 1. /areas ---
st, hd, body, url = get("/areas")
areas = jload(body)
print(f"[areas] {st} {url} top-level count={len(areas)}")
open(f"{SCRATCH}/areas.json", "w").write(body)

wanted = {"Казахстан": None, "Россия": None, "Алматы": None, "Астана": None}
def walk(node, parent):
    if node["name"] in wanted and wanted[node["name"]] is None:
        wanted[node["name"]] = (node["id"], parent)
    for ch in node.get("areas", []):
        walk(ch, node["name"])
for c in areas:
    walk(c, None)
for name, v in wanted.items():
    print(f"  area: {name!r} -> id={v[0]} (parent={v[1]})")

kz = wanted["Казахстан"][0]
ru = wanted["Россия"][0]

# --- 2. KZ search, per_page=100 (max) ---
st, hd, body, url = get("/vacancies", {"text": "python", "area": kz, "per_page": 100, "page": 0})
d = jload(body)
open(f"{SCRATCH}/kz_python.json", "w").write(body)
print(f"\n[kz python per_page=100] {st} {url}")
print(f"  found={d['found']} pages={d['pages']} per_page={d['per_page']} page={d['page']} items={len(d['items'])}")
print(f"  item0 keys: {sorted(d['items'][0].keys())}")
for it in d["items"][:3]:
    print(f"  salary sample id={it['id']}: salary={json.dumps(it.get('salary'), ensure_ascii=False)} | salary_range={json.dumps(it.get('salary_range'), ensure_ascii=False)}")

# --- 3. RU search example ---
st, hd, body, url = get("/vacancies", {"text": "python", "area": ru, "per_page": 1})
d = jload(body)
print(f"\n[ru python] {st} {url}")
print(f"  found={d['found']} pages={d['pages']} per_page={d['per_page']}")

# --- 4. per_page=200 ---
st, hd, body, url = get("/vacancies", {"text": "python", "area": kz, "per_page": 200})
print(f"\n[per_page=200] {st} {url}")
d = jload(body)
if st == 200:
    print(f"  NO ERROR: found={d['found']} per_page={d['per_page']} items={len(d['items'])} pages={d['pages']}")
else:
    print(f"  body: {body[:600]}")

# --- 5. depth: RU no text, page=19 then page=20 (per_page=100) ---
st, hd, body, url = get("/vacancies", {"area": ru, "per_page": 100, "page": 19})
d = jload(body)
print(f"\n[depth page=19] {st} {url}")
if st == 200:
    print(f"  found={d['found']} pages={d['pages']} items={len(d['items'])}")
else:
    print(f"  body: {body[:600]}")

st, hd, body, url = get("/vacancies", {"area": ru, "per_page": 100, "page": 20})
print(f"\n[depth page=20] {st} {url}")
print(f"  body: {body[:800]}")
