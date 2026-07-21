"""All ETL constants. Single source of truth for the pipeline (see PLAN.md §3.4)."""

USER_AGENT = "tech-salary-radar/1.0 (+https://github.com/midat-fx/tech-salary-radar; midat.faizov@gmail.com)"

# Public, no-auth ATS job-board endpoints. {slug} = company board slug (verified live 18.07, see §4).
SOURCES = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
    "lever":      "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby":      "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
}
SEED_PATH = "data/seed_companies.json"     # [{ "source": ..., "slug": ..., "name": ... }]

FETCH_PAUSE_SEC = 0.5          # + jitter 0.2-0.4 in code; one request per board
HTTP_TIMEOUT = 20

# Salary normalization -> annual gross USD (see §5)
HOURS_PER_YEAR = 2080
WEEKS_PER_YEAR = 52
MONTHS_PER_YEAR = 12
SALARY_MIN_USD = 10_000        # sanity floor: annual mid below this is dropped as garbage
SALARY_MAX_USD = 1_500_000     # sanity ceiling: annual mid above this is dropped

# LLM
LLM_MODEL = "gemini-3.1-flash-lite"   # 2.5-flash-lite is closed to new API keys (see journal)
LLM_BATCH_SIZE = 10            # small batch: long English JDs (requirements live mid/end of text)
LLM_PAUSE_SEC = 8.0
LLM_DAILY_JOB_LIMIT = 5000     # = 500 calls at batch 10; ceiling is 900 calls/day (free tier)
LLM_TEXT_TRIM = 4000           # description chars per job (JDs are long; 1500 cut the requirements)
PROMPT_VERSION = "v1"

FX_MAX_AGE_DAYS = 3
TZ = "Asia/Almaty"
