import sys, json
sys.path.insert(0, "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh")
from hhlib import get, jload

SCRATCH = "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh"
KZ, RU = 40, 113

def show(tag, st, url, d, body):
    print(f"\n[{tag}] HTTP {st}\n  URL: {url}")
    if st == 200 and d and "found" in d:
        print(f"  found={d['found']} pages={d.get('pages')} per_page={d.get('per_page')} page={d.get('page')} items={len(d.get('items', []))}")
    else:
        print(f"  body: {body[:700]}")
    return d

# 1. KZ python, per_page=100
st, hd, body, url = get("/vacancies", {"text": "python", "area": KZ, "per_page": 100, "page": 0})
d = jload(body)
show("KZ python per_page=100", st, url, d, body)
if st == 200:
    open(f"{SCRATCH}/kz_python.json", "w").write(body)
    it = d["items"][0]
    print("  item0 keys:", sorted(it.keys()))

# 2. RU python
st, hd, body, url = get("/vacancies", {"text": "python", "area": RU, "per_page": 1})
show("RU python", st, url, jload(body), body)

# 3. per_page=200
st, hd, body, url = get("/vacancies", {"text": "python", "area": KZ, "per_page": 200})
show("per_page=200", st, url, jload(body), body)

# 4-5. depth 2000: RU no text
st, hd, body, url = get("/vacancies", {"area": RU, "per_page": 100, "page": 19})
show("RU page=19 per_page=100 (items 1901-2000)", st, url, jload(body), body)
st, hd, body, url = get("/vacancies", {"area": RU, "per_page": 100, "page": 20})
show("RU page=20 per_page=100 (>2000)", st, url, jload(body), body)

# 6. date_from/date_to with hours (KZ python)
for tag, params in [
    ("date_from=16T00:00+0500", {"text": "python", "area": KZ, "per_page": 0, "date_from": "2026-07-16T00:00:00+0500"}),
    ("date_from=16T12:00+0500", {"text": "python", "area": KZ, "per_page": 0, "date_from": "2026-07-16T12:00:00+0500"}),
    ("16T00..16T12 from+to",    {"text": "python", "area": KZ, "per_page": 0, "date_from": "2026-07-16T00:00:00+0500", "date_to": "2026-07-16T12:00:00+0500"}),
]:
    st, hd, body, url = get("/vacancies", params)
    show(tag, st, url, jload(body), body)

# 7. operators
for tag, text in [
    ("OR", "python OR javascript"),
    ("phrase-unquoted", "machine learning"),
    ("phrase-quoted", '"machine learning"'),
    ("parens+NOT", "(python OR javascript) NOT senior"),
]:
    st, hd, body, url = get("/vacancies", {"text": text, "area": KZ, "per_page": 0})
    show(f"text {tag}: {text}", st, url, jload(body), body)

# 8. host param
st, hd, body, url = get("/vacancies", {"text": "python", "area": KZ, "per_page": 0, "host": "hh.kz"})
show("host=hh.kz", st, url, jload(body), body)

# 9. api.hh.kz alias
st, hd, body, url = get("/vacancies", {"text": "python", "area": KZ, "per_page": 0}, base="https://api.hh.kz")
show("api.hh.kz alias", st, url, jload(body), body)
