"""Build & live-validate data/seed_companies.json from candidate slugs across the 3 ATS.

status: active (200 & >=1 job) | empty (200, 0 jobs) | dead (404/other).
Also records n_jobs and rough has_eu / has_remote signals (sampled from job locations).
Dedup by normalized company name, preferring an active board.
"""
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

UA = "tech-salary-radar/1.0 (+https://github.com/midat-fx/tech-salary-radar; midat.faizov@gmail.com)"
ADDED = "2026-07-18"
OUT = Path(__file__).resolve().parents[2] / "data" / "seed_companies.json"

EU = ["united kingdom", "england", "london", "germany", "berlin", "munich", "france", "paris",
      "spain", "madrid", "barcelona", "netherlands", "amsterdam", "ireland", "dublin", "poland",
      "warsaw", "sweden", "stockholm", "portugal", "lisbon", "italy", "rome", "milan", "belgium",
      "brussels", "austria", "vienna", "denmark", "copenhagen", "finland", "helsinki", "norway",
      "oslo", "czech", "prague", "romania", "bucharest", "estonia", "tallinn", "lithuania",
      "latvia", "greece", "hungary", "budapest", "switzerland", "zurich", "zürich", "luxembourg",
      "bulgaria", "croatia", "slovakia", "slovenia", "eu remote", "emea"]

GREENHOUSE = """stripe airbnb gitlab databricks coinbase cloudflare figma dropbox robinhood instacart
doordash reddit discord lyft twitch snowflake samsara benchling gusto affirm chime sofi betterment
asana box docusign elastic hashicorp confluent datadog mongodb newrelic pagerduty twilio okta fastly
digitalocean circleci launchdarkly segment amplitude fivetran airbyte hex retool webflow zapier
airtable coda miro canva grammarly duolingo quizlet chegg coursera flexport gopuff faire whatnot
rippling gong outreach lattice cultureamp pilot mercury checkr verkada anthropic gitpod typeform
pleo trustpilot mollie mews messagebird docplanner sumup celonis contentful aiven personio revolut
wise monzo gocardless deliveroo bolt wolt klarna cockroachlabs clickhouse temporal grafanalabs
render supabase planetscale neon railway posthog sourcegraph doppler tailscale warp browserbase
modal together weightsandbiases scale huggingface glean sierra harvey abridge cursor perplexity
mistral runway pika suno elevenlabs synthesia deepgram assemblyai pinecone weaviate chroma
lightning cohere adept imbue character 11x decagon writer jasper copy typeface
robloxcorporation unity nianticlabs epicgames discord patreon substack ghost buffer hootsuite
squarespace webflow framer bubble airtable notion coda mem tana reflect capacities
brex ramp mercury column modern treasury unit increase lithic marqeta highnote
gemini kraken circle fireblocks chainalysis alchemy blockchain consensys phantom uniswaplabs""".split()

LEVER = """palantir matchgroup nubank mercadolibre quora kickstarter shopify github atlassian
plaid netflix eventbrite reddit spotify twitch discord kayak yelp thumbtack nerdwallet
sofi affirm chime brex ramp mercury plaid robinhood coinbase kraken gemini circle
attentive ramp swanest sardine finix modern-treasury unit-finance highnote lithic
leadgenius voleon hometap cambly getlago hightouch census rudderstack metabase
fingerprint workato tray postman kong tyk apollo hasura temporal-technologies
notion vercel linear replit ashby retool webflow supabase render railway fly
canva miro figma pitch gamma tome beautiful descript loom mmhmm
scaleapi huggingface cohere anthropic openai adept together mistral runway
turing andela toptal gitlab remotecom deel oyster remote workmotion multiplier
brave duckduckgo mozilla protonmail signalapp tor cloudflare fastly bunny""".split()

ASHBY = """ramp notion linear replit openai vercel deel hex clay watershed baseten modal
runway pika suno elevenlabs synthesia deepgram assemblyai together mistral perplexity
glean sierra harvey abridge cursor anysphere decagon writer typeface eleven
cohere adept imbue character 11x mercor braintrust langchain llamaindex weaviate
pinecone chroma qdrant zilliz fireworks anyscale predibase lightning replicate
supabase neon planetscale turso xata railway render flyio browserbase e2b
posthog june amplitude statsig launchdarkly flagsmith unleash
mercury column ramp brex arc puzzle rippling deel remote gusto rho relay
vanta drata secureframe sprinto tailscale teleport doppler infisical
zip ashby gem greenhouse-software rippling deel navan brex mercury
watershed patch persefoni sylvera pachama crux normal sardine unit0
scale surge labelbox snorkel humanloop weightsandbiases wandb comet arize
whatnot faire flexport shippo easypost sourcegraph warp fig charm""".split()

CANDIDATES = {"greenhouse": GREENHOUSE, "lever": LEVER, "ashby": ASHBY}
URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{s}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{s}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{s}?includeCompensation=true",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def jobs_and_locs(ats, body):
    try:
        d = json.loads(body)
    except Exception:
        return None, []
    if ats == "lever":
        jobs = d if isinstance(d, list) else []
        locs = [((j.get("categories") or {}).get("location") or "") + " " + (j.get("workplaceType") or "") for j in jobs[:25]]
    elif ats == "greenhouse":
        jobs = d.get("jobs", []) if isinstance(d, dict) else []
        locs = [((j.get("location") or {}).get("name") or "") for j in jobs[:25]]
    else:
        jobs = d.get("jobs", []) if isinstance(d, dict) else []
        locs = [((j.get("location") or "") + (" remote" if j.get("isRemote") else "")) for j in jobs[:25]]
    return len(jobs), [x.lower() for x in locs]


rows = []
seen = set()
for ats, slugs in CANDIDATES.items():
    for slug in sorted(set(slugs)):
        code, body = get(URLS[ats].format(s=slug))
        n, locs = jobs_and_locs(ats, body)
        if code == 200 and n is not None and n > 0:
            status = "active"
        elif code == 200:
            status = "empty"
        else:
            status = "dead"
        has_eu = any(any(tok in loc for tok in EU) for loc in locs)
        has_remote = any("remote" in loc for loc in locs)
        rows.append({"name": slug, "ats": ats, "slug": slug, "status": status,
                     "added": ADDED, "n_jobs": n or 0, "has_eu": has_eu, "has_remote": has_remote})
        print(f"{ats:10} {slug:22} {code} n={n} {status} eu={int(has_eu)} rem={int(has_remote)}")
        time.sleep(0.35)

# dedup by normalized name, prefer active
best = {}
for r in rows:
    key = r["name"].lower()
    cur = best.get(key)
    if cur is None or (r["status"] == "active" and cur["status"] != "active"):
        best[key] = r
final = sorted(best.values(), key=lambda r: (r["ats"], r["slug"]))

active = [r for r in final if r["status"] == "active"]
eu = [r for r in active if r["has_eu"]]
rem = [r for r in active if r["has_remote"]]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(final, ensure_ascii=False, indent=2))
print("\n==== SUMMARY ====")
print(f"candidates probed: {len(rows)} | after dedup: {len(final)}")
print(f"ACTIVE: {len(active)} | empty: {sum(1 for r in final if r['status']=='empty')} | dead: {sum(1 for r in final if r['status']=='dead')}")
by = {}
for r in active:
    by[r["ats"]] = by.get(r["ats"], 0) + 1
print(f"active by ats: {by}")
print(f"active with EU jobs: {len(eu)} ({100*len(eu)//max(1,len(active))}%) | with remote: {len(rem)} ({100*len(rem)//max(1,len(active))}%)")
print(f"total active jobs: {sum(r['n_jobs'] for r in active)}")
print(f"written: {OUT}")
