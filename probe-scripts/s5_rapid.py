import sys, time, json
sys.path.insert(0, "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh")
from hhlib import get, jload

KZ = 40
print("=== 10 rapid requests, no pauses ===")
first_headers = None
for i in range(1, 11):
    t0 = time.time()
    st, hd, body, url = get("/vacancies", {"text": "python", "area": KZ, "per_page": 1}, pause=False)
    dt = time.time() - t0
    ratey = {k: v for k, v in hd.items() if any(s in k.lower() for s in ["limit", "retry", "quota", "captcha"])}
    print(f"req {i:2d}: HTTP {st} {dt:.2f}s rate-headers={ratey or 'none'}")
    if i == 1:
        first_headers = hd
    if st != 200:
        print("   BODY:", body[:400])
        print("   HEADERS:", json.dumps(dict(hd), ensure_ascii=False)[:800])

print("\n=== all header names of response 1 ===")
for k, v in (first_headers or {}).items():
    print(f"  {k}: {v[:100]}")

print("\n=== polite request 3s after the burst ===")
time.sleep(3)
st, hd, body, url = get("/vacancies", {"text": "python", "area": KZ, "per_page": 1}, pause=False)
d = jload(body)
print(f"HTTP {st} found={d.get('found') if st==200 and d else body[:200]}")
