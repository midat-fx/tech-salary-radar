import sys, time, json, datetime
sys.path.insert(0, "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh")
from hhlib import get

LOG = "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh/retry_log.txt"

def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}\n")

for attempt in range(1, 13):
    st, hd, body, url = get("/vacancies", {"text": "python", "area": 40, "per_page": 1}, pause=False)
    log(f"attempt={attempt} status={st} body={body[:120]}")
    if st == 200:
        log("UNBANNED")
        print("UNBANNED")
        sys.exit(0)
    if attempt < 12:
        time.sleep(240)
log("STILL_BANNED")
print("STILL_BANNED")
sys.exit(1)
