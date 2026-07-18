import sys, json
sys.path.insert(0, "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh")
from hhlib import get, jload

KZ = 40
queries = [
    'machine learning OR "машинное обучение" OR "data scientist"',
    '"data engineer" OR ETL OR airflow',
    '"data analyst" OR "аналитик данных" OR SQL',
    'backend OR бэкенд',
    'DevOps',
    'LLM OR "искусственный интеллект" OR нейросет*',
    'автоматизация OR RPA OR n8n',
]
for q in queries:
    st, hd, body, url = get("/vacancies", {"text": q, "area": KZ, "per_page": 0})
    d = jload(body)
    found = d.get("found") if (st == 200 and d) else f"HTTP {st}: {body[:200]}"
    print(f"found={found}\ttext={q!r}")
    print(f"   URL: {url}")

# search_field=name narrowing demo
st, hd, body, url = get("/vacancies", {"text": "python", "area": KZ, "per_page": 0, "search_field": "name"})
d = jload(body)
print(f"found={d.get('found') if st==200 else body[:200]}\ttext='python' + search_field=name")
print(f"   URL: {url}")
