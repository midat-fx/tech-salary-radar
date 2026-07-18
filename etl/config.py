"""All ETL constants. Single source of truth for the pipeline (see PLAN.md §3.4)."""

import os

HH_BASE = os.environ.get("HH_BASE", "https://api.hh.ru")
USER_AGENT = "salary-radar-kz/1.0 (+https://github.com/midat-fx/salary-radar-kz; midat.faizov@gmail.com)"
AREAS = {"kz": 40, "ru": 113}                      # id confirmed live 18.07
SEARCH_KEYS = {  # order = dedup priority
    "ml_ai":   '"machine learning" OR ML OR AI OR LLM OR "искусственный интеллект" OR нейросет* OR "computer vision" OR NLP',
    "data":    '"data engineer" OR "data scientist" OR "data analyst" OR "аналитик данных" OR "инженер данных" OR "дата-сайентист" OR "дата-инженер"',
    "python":  'python OR питон OR django OR fastapi',
    "devops":  'devops OR SRE OR kubernetes',
    "backend": 'backend OR бэкенд OR back-end OR java OR "node.js" OR golang OR "c#" OR php OR ".net"',
    "frontend": 'frontend OR фронтенд OR front-end OR react OR vue OR angular OR верстальщик',
    "mobile":  'android OR ios OR flutter OR "react native"',
    "qa":      'QA OR тестировщик OR "test engineer" OR автотест*',
    "analyst": '"бизнес-аналитик" OR "системный аналитик" OR "BI-аналитик" OR "продуктовый аналитик" OR "product analyst"',
    "one_c":   '"1С" OR "1C"',
    "dev_other": 'разработчик OR программист OR developer OR "software engineer"',
}
SEARCH_PLAN = {"kz": list(SEARCH_KEYS), "ru": ["ml_ai", "data"]}
PER_PAGE = 100
MAX_PAGES = 20
DEPTH_SPLIT_THRESHOLD = 1900
SEARCH_PAUSE_SEC = 1.0          # + jitter 0.2-0.4 in code
DETAIL_LIMIT = 400
DETAIL_PAUSE_SEC = 1.0
BACKFILL_DAYS = 35              # hh archive is not deeper (see PLAN.md §9)
LLM_MODEL = "gemini-2.5-flash-lite"
LLM_BATCH_SIZE = 20
LLM_PAUSE_SEC = 8.0
LLM_DAILY_VACANCY_LIMIT = 1200  # = 60 calls; never exceed the 900 daily call ceiling
LLM_TEXT_TRIM = 1500            # description chars per vacancy
PROMPT_VERSION = "v1"
FX_MAX_AGE_DAYS = 3
TZ = "Asia/Almaty"
