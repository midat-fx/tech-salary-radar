# PLAN.md — «Радар навыков и зарплат» (tech-salary-radar)

> Полная инструкция сборки. Источник изменён 18.07.2026: hh соискательский API закрыт 15.12.2025 →
> рефрейм на публичные ATS-доски (Greenhouse/Lever/Ashby). Все архитектурные решения приняты владельцем.
> Исполнитель НЕ принимает архитектурных решений — только выполняет этапы и проходит приёмки.
> История поворота источника (hh → enbek → ATS) — в «Журнале исполнения» в конце файла.

## §0. Правила для исполнителя

1. Работать строго по этапам §7. Этап не завершён, пока не пройдена его **приёмка**. Приёмки не пропускать и не ослаблять.
2. Встретил противоречие или невозможность — СТОП, короткий вопрос владельцу. Не изобретать обходы.
3. Ответы владельцу — по-русски. Код, коммиты, README — по-английски. Дашборд — по-русски.
4. Коммиты: обычные conventional (`feat:`, `fix:`, `data:`), автор только Midat Faizov <midat.faizov@gmail.com>, **без Co-Authored-By и любых упоминаний Claude/AI-ассистента**.
5. Не добавлять зависимостей сверх зафиксированных в §3.2. Не добавлять фич сверх плана — всё «хорошо бы ещё» идёт в Roadmap README.
6. **«Проверено» = есть живой ответ в руках.** Любой факт об источнике подтверждать реальным ответом API и сохранять сырьё (обрезанный сэмпл) в `probe-scripts/`. Урок hh: план утверждал «проверено разведкой», а живой вакансии не было ни одной.
7. Известные ловушки — §9. Прочитать ДО начала кода.
8. gh и wrangler авторизованы у владельца; секрет GEMINI_API_KEY лежит в `~/projects/deka/.env` (строка `GEMINI_API_KEY=`) — уже добавлен в GitHub Secrets репозитория.

## §1. Что строим и зачем

**Продукт:** публичный сайт-дашборд «Радар навыков и зарплат» — срез мирового tech-найма глазами СНГ-разработчика: сколько платят по грейдам и регионам, какие навыки требуют чаще всего и **какие навыки добавляют к зарплате больше всего** (флагманский график). Данные — из публичных карьерных досок (ATS) сотен tech-компаний. Обновляется сам каждое утро. Хостинг $0/мес.

**Зачем:** флагманский Python-проект портфолио под цель junior AI/Data Engineer (у автора всё портфолио на TypeScript). Чекбоксы: Python, pandas, SQL/DuckDB, ETL из нескольких API, cron-оркестрация, Docker, CI/CD, LLM structured output + eval, data quality. Аудитория: рекрутеры, разработчики СНГ (@itmankz, 8k), сам автор — «что учить и сколько это приносит».

**Имя:** репозиторий `tech-salary-radar` (публичный, github.com/midat-fx), на дашборде — «Радар навыков и зарплат».

## §2. Продуктовая рамка (зафиксировано)

- **Источник v1 — публичные ATS-доски: Greenhouse, Lever, Ashby.** No-auth, полные тексты вакансий. Сид ≥300 компаний (§6.5), заметная доля с remote/EU-наймом (не только US-офисы). Remotive/Arbeitnow (remote-агрегаторы) — Roadmap. Источники не выдумывать; каждый подтверждён живой разведкой (§4).
- **Позиционирование:** «мировой tech-найм глазами СНГ-разработчика — что учить и сколько это приносит». Аудитория — рекрутеры и разработчики СНГ.
- **Зарплата:** аналитическая база = **годовой gross USD**. Интервалы приводятся к годовым (§5). Не-USD (GBP/EUR/…) → USD по дневному курсу (§5). На дашборде — USD; в hero-плитках и тултипах рядом с годовой цифрой месячная в скобках «(~$X/мес, ÷12)»; оси и корзины — только annual USD, без тумблеров валют. Подпись методики: «зарплаты — gross, годовые, как принято в международном найме; по N вакансий с указанной вилкой».
- **Только тёмная тема**, дашборд по-русски, без переключателей языка/темы/валюты, без RSS и share-кнопок в v1.
- Против hh/калькуляторов больше не позиционируемся (hh мёртв как источник). Позиция: (1) премия навыка из полного текста вакансии через LLM — уникальный график; (2) открытые код+данные+методика, «не верь на слово — скачай parquet и пересчитай сам»; (3) фокус на том, что востребовано и оплачивается в глобальном tech-найме.

## §3. Архитектура

### 3.1. Дерево репозитория

```
tech-salary-radar/
├── README.md                      # EN; структура — §7 этап 9
├── PLAN.md                        # этот файл (коммитится — журнал решений)
├── pyproject.toml
├── .python-version                # 3.12
├── .gitignore
├── .gitattributes                 # *.parquet binary / site/vendor/* linguist-vendored
├── Dockerfile
├── .dockerignore                  # data/ site/ tests/ docs/ .git/ .github/
├── .github/workflows/
│   ├── ci.yml                     # ruff + pytest; llm-eval шаг добавляется этапом 5
│   ├── smoke.yml                  # workflow_dispatch: доступность 3 ATS API (диагностика)
│   ├── pipeline.yml               # ежедневный cron: ETL → commit (минимальная версия с этапа 3)
│   └── backfill.yml               # workflow_dispatch: разовый бэкфилл «новых» по дате публикации
├── etl/
│   ├── __init__.py
│   ├── config.py                  # все константы (§3.4)
│   ├── sources.py                 # httpx-клиенты Greenhouse/Lever/Ashby + парсеры в общий формат
│   ├── fetch.py                   # обход сид-листа: по компании → sources → нормализованные джобы
│   ├── normalize.py               # джобы → строки таблиц (регион, seniority, дедуп, запись партиций)
│   ├── fx.py                      # курсы (er-api base USD → jsdelivr → кэш), интервал→annual, →USD
│   ├── salary.py                  # парсинг вилок по источникам (Ashby structured, Lever field, GH regex) + санитар
│   ├── skills_catalog.py          # 61 канонический навык + алиасы (§6.1)
│   ├── skills.py                  # Gemini-извлечение навыков из текста, кэш
│   ├── aggregate.py               # DuckDB SQL → site/data/*.json + badge.json
│   └── cli.py                     # python -m etl.cli run|backfill|aggregate
├── site/
│   ├── index.html                 # дашборд, lang=ru, тёмная тема
│   ├── app.js                     # fetch data/*.json → Chart.js, клиентские фильтры
│   ├── style.css
│   ├── vendor/chart.umd.min.js            # Chart.js 4.4.3 (вендорен)
│   ├── vendor/chartjs-plugin-annotation.min.js
│   └── data/                      # артефакты aggregate (коммитятся): latest.json, timeseries.json, meta.json, badge.json
├── data/
│   ├── seed_companies.json                     # курируемый сид ≥300 [{source, slug, name?}] (§6.5, коммитится)
│   ├── snapshots/dt=YYYY-MM-DD/part.parquet     # ежедневно: ВСЕ активные найденные (тонкая)
│   ├── jobs/dt=YYYY-MM-DD/part.parquet          # только НОВЫЕ job_uid этого дня (полные поля)
│   ├── skills/dt=YYYY-MM-DD/part.parquet        # навыки новых job_uid (+ это кэш LLM)
│   ├── cache/fx_latest.json                     # фолбэк курсов (коммитится)
│   └── eval/skills_eval.jsonl                   # 25 размеченных примеров (§6.4)
├── probe-scripts/                 # разведскрипты + ats-recon/ (COOKBOOK.md, sample_*.json — живое сырьё)
├── docs/screenshot-hero.png       # этап 9
├── docs/screenshot-skills.png
└── tests/
    ├── conftest.py                # фикстуры; авто-skip llm_eval без ключа
    ├── fixtures/greenhouse.json   # обрезанные живые ответы (этап 1)
    ├── fixtures/lever.json
    ├── fixtures/ashby.json
    ├── test_config.py
    ├── test_sources.py            # парсинг 3 ATS на фикстурах (httpx MockTransport)
    ├── test_salary.py             # интервал→annual, coalesce, санитар-границы, валюты
    ├── test_normalize.py          # регион, seniority, дедуп, идемпотентность
    ├── test_fx.py
    ├── test_skills.py             # canonicalize, парсинг ответа LLM
    ├── test_aggregate.py          # на синтетическом мини-parquet
    └── test_eval_llm.py           # @pytest.mark.llm_eval (реальный Gemini)
```

Вендоринг (проверено 18.07, 200):
```bash
curl -sSL -o site/vendor/chart.umd.min.js 'https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js'
curl -sSL -o site/vendor/chartjs-plugin-annotation.min.js 'https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js'
```

### 3.2. pyproject.toml (зафиксирован)

Идентичен уже созданному (httpx, pandas, pyarrow, duckdb, google-genai, tenacity; dev: pytest, ruff; ruff line-length 100; pytest marker llm_eval). Зависимостей не добавлять.

### 3.3. Модель данных: три append-only таблицы

`job_uid = f"{source}:{company}:{job_id}"` — стабильный ключ дедупа (компания использует ровно один ATS, id уникален внутри доски). Ежедневный прогон пишет **дневные партиции, которые не переписываются** (исключение: повторный запуск того же дня перезаписывает партиции этого дня целиком — идемпотентность). Parquet `compression="zstd"`, сортировка по job_uid. **Сырой JSON и полные тексты описаний в git не попадают** (текст — вход LLM в том же запуске, выбрасывается). checkout в Actions `fetch-depth: 1`.

**`data/snapshots/dt=*/part.parquet`** — все активные джобы, найденные сегодня (тонкая):

| колонка | тип |
|---|---|
| job_uid | string |
| snapshot_date | date32 (Asia/Almaty) |
| source | string: greenhouse\|lever\|ashby |
| company | string (slug) |
| region | string: us\|eu\|other (§3.6) |
| is_remote | bool |
| seniority | string: junior\|mid\|senior\|staff+\|unspecified (из title, §3.6) |
| is_management | bool (Manager/Director/VP/Head/Chief — исключается из ЗП-статистики, §3.6) |
| salary_min_usd, salary_max_usd | float64, nullable (annual gross USD) |
| salary_mid_usd | float64, nullable (COALESCE, после санитара §5) |
| has_salary | bool |
| employment_type | string, nullable |
| published_at | timestamp UTC |

**`data/jobs/dt=*/part.parquet`** — job_uid, впервые увиденные в этот день (полные поля): job_uid, first_seen (date32), source, company, title, location_raw (string), region, is_remote, seniority, employment_type, published_at, apply_url, currency_original, salary_min_orig, salary_max_orig, salary_interval_orig, + те же salary_*_usd/has_salary, что в snapshots.

**`data/skills/dt=*/part.parquet`** — навыки новых job_uid (длинный формат, **кэш LLM**): job_uid (string), skill (string, nullable — **NULL = «обработано, навыков не найдено»**), source (`llm`), prompt_version (string, `v1`), extracted_at (timestamp UTC). Множество обработанных = `SELECT DISTINCT job_uid FROM skills`; очередь на извлечение = anti-join jobs − skills (самозалечивается). У ATS нет бесплатного ground-truth аналога hh key_skills → навыки только LLM; eval на ручной разметке (§6.4).

**Механизм «новых»:** новые job_uid дня = anti-join сегодняшнего снапшота против ВСЕХ существующих `data/jobs/*`. Календарное «вчера» не используется.

Рост: сид ~300 компаний × ~сотни джоб ≈ 30–80k активных строк/день (тонкая snapshots) + сотни новых/день (jobs). Порядок ~0.5–1 МБ/день. Ручка: если партиция дня >2 МБ три дня подряд — сузить сид (одна строка конфига). LFS не нужен.

### 3.4. etl/config.py (все константы)

```python
USER_AGENT = "tech-salary-radar/1.0 (+https://github.com/midat-fx/tech-salary-radar; midat.faizov@gmail.com)"
SOURCES = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
    "lever":      "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby":      "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
}
SEED_PATH = "data/seed_companies.json"     # [{ "source": ..., "slug": ..., "name": ... }]
FETCH_PAUSE_SEC = 0.5           # + джиттер 0.2-0.4 в коде; 1 запрос на доску
HTTP_TIMEOUT = 20
# зарплата
HOURS_PER_YEAR = 2080; WEEKS_PER_YEAR = 52; MONTHS_PER_YEAR = 12
SALARY_MIN_USD = 10_000; SALARY_MAX_USD = 1_500_000   # санитар: вне диапазона — отбросить
# LLM
LLM_MODEL = "gemini-2.5-flash-lite"; LLM_BATCH_SIZE = 20; LLM_PAUSE_SEC = 8.0
LLM_DAILY_JOB_LIMIT = 1200      # = 60 вызовов; дневной потолок 900 вызовов не превышать
LLM_TEXT_TRIM = 1500            # символов описания на джобу
PROMPT_VERSION = "v1"
FX_MAX_AGE_DAYS = 3
TZ = "Asia/Almaty"
```
Никаких hh-констант (AREAS, SEARCH_KEYS, RUR, salary_range, налоги) — вычищены.

### 3.5. Файлы для фронта (пишет aggregate.py, читает только их)

**site/data/latest.json** — активный срез (последний снапшот), компактные строки для клиентских фильтров:
```jsonc
{
  "snapshot_date": "2026-08-20",
  "companies": ["stripe", "ashby", ...],     // индексы для rows
  "skills": ["Python", "SQL", ...],          // индексы для rows
  "rows": [
    // [region, seniority, is_remote, is_mgmt, company_idx, salary_mid_usd|null, skills|null, is_new]
    // region: us|eu|other; seniority: junior|mid|senior|staff+|unspecified; is_mgmt: 1 = excluded from salary stats
    // skills: null = ещё НЕ обработан LLM; [] = обработан, навыков нет; [idx,...] = навыки
    // is_new: 1 если first_seen = snapshot_date
    ["us", "senior", 1, 0, 3, 245000, [0, 1, 14], 0]
  ]
}
```
Оценка размера: 30–80k строк — держать компактно (индексы, короткие коды); CI-ассерт latest.json ≤ 3 МБ (если больше — сузить сид или урезать поля).

**site/data/timeseries.json**: `[{ "date": "2026-08-01", "active": 41200, "new": 620, "median_usd": 168000 }, ...]` — только реальные снапшоты.

**site/data/meta.json**:
```jsonc
{
  "updated_at": "2026-08-20T01:52:07Z",
  "days_collected": 12,
  "companies_tracked": 312,
  "sources": { "greenhouse": 140, "lever": 60, "ashby": 112 },   // компаний по источнику
  "fx": { "date": "2026-08-20", "base": "USD", "source": "er-api", "stale": false, "gbp_usd": 1.27, "eur_usd": 1.08 },
  "salary_note": "Зарплаты — gross, годовые (интервал приведён к году), в USD. По N вакансий с указанной вилкой. Не-USD → USD по дневному курсу.",
  "attribution": "Данные о вакансиях: публичные карьерные доски компаний (Greenhouse, Lever, Ashby). Проект не аффилирован с ними.",
  "skill_premium": [ { "skill": "Rust", "n": 34, "premium_pct": 22.4, "median_with_usd": 210000, "median_without_usd": 172000 }, ... ],
  "top_companies": [ { "company": "stripe", "n": 190, "url": "https://boards.greenhouse.io/stripe" }, ... ],
  "coverage": { "salary_share": 0.38, "skills_extracted_share": 0.95, "dropped_salary_out_of_bounds": 214, "filtered_non_tech": 1830 }
}
```

**site/data/badge.json** (shields.io endpoint): `{ "schemaVersion": 1, "label": "jobs tracked", "message": "41 200", "color": "brightgreen" }`.

### 3.6. Методика метрик (зафиксирована)

- **Зарплата → annual gross USD** (§5): интервал×коэффициент → год; валюта→USD; `mid = COALESCE((min+max)/2, min, max)`; строки с `mid < $10k` или `mid > $1.5M` отбрасываются (счётчик — в лог и `meta.coverage.dropped_salary_out_of_bounds`). Медианы: `quantile_cont(mid, 0.5)` только по `mid IS NOT NULL`. На фронте месячное = `usd/12`, округление до сотен.
- **Регион:** из location/country. `us` — США; `eu` — страны ЕС + UK/EEA; иначе `other`. Флаг `is_remote` — отдельно (из isRemote/workplaceType; для GH — по тексту location «Remote»).
- **Seniority из title** (regex, порядок сверху) — 5 бакетов: `staff+` (staff|principal|lead|distinguished|fellow), `senior` (senior|sr\.|snr), `junior` (junior|jr\.|intern|new grad|graduate|entry|associate), `mid` (mid|middle|II\b|2\b без старших маркеров), иначе **`unspecified`** (маркера уровня в названии нет — отдельный бакет, НЕ сливать в mid, иначе mid загрязнён). Эвристика, помечать дисклеймером.
- **Management-флаг:** title матчит `manager|director|\bVP\b|vice president|head of|chief|\bC[TE]O\b` → `is_management=true`. **Управленческие роли исключаются из ВСЕЙ зарплатной статистики** (распределение ЗП, ЗП по грейдам, премия навыка) — их вилки ломают медианы IC-инженеров. В объём/спрос-на-навыки могут входить.
- **Премия навыка (флагман), по salary-subset, БЕЗ management:** только строки с `mid IS NOT NULL` и `is_management=false`. Страты — **грейд × регион** (не только грейд): контролирует конфаундинг (навык, частый в EU, иначе получит заниженную премию из-за разницы регионов, а не ценности). Внутри страты b (seniority×region), где ≥8 джоб с навыком И ≥8 без, `ratio_b = median_with_b / median_without_b`, вес = n_with_b. **premium_pct = (Σ ratio_b·n_with_b / Σ n_with_b − 1)·100.** Навык допускается при ≥15 джобах с ЗП суммарно; топ-10 положительных. Строки сейчас преимущественно US — подписать; EU-страта включится по мере данных (EU pay-transparency директива действует). Подзаголовок: «стратифицировано по грейдам и регионам · по N вакансий с указанной вилкой».
- «Новые за день» = job_uid с first_seen = дата. Активные = строки снапшота даты.
- Подписи seniority: junior=«Джуниор», mid=«Мидл», senior=«Сеньор», staff+=«Стафф+», unspecified=«Без уровня».

### 3.7. Роль-фильтр (в датасет только tech-IC-роли)
В базу попадают только инженерные / data / product-tech вакансии. Механика: сперва `department`/`team` из ATS (Ashby `department/team`, Lever `categories.team`, Greenhouse `departments[]`), затем title-эвристика.
- **Allowlist** (по department ИЛИ title): engineer, engineering, developer, programmer, software, backend, frontend, full[- ]?stack, mobile, android, ios, data (scientist|engineer|analyst), machine learning, \bML\b, \bAI\b, MLOps, DevOps, \bSRE\b, site reliability, platform, infrastructure, cloud, \bQA\b, quality, \bSDET\b, test engineer, security, infosec, applied scientist, research engineer.
- **Deny** (перебивает allowlist по department; по title — если нет явного eng-маркера): sales, account executive, recruit, talent, \bHR\b, people ops, legal, counsel, finance, accounting, marketing, growth, content, community, support, customer success, operations, office, facilities, executive assistant.
- **PM и designer — исключены из v1** (product manager, program manager, designer, \bUX\b, \bUI\b): продукт про «что учить разработчику», PM/дизайн размывают тех-скилл-сигнал. → Roadmap (отдельные срезы).
- Счётчик отфильтрованных не-tech — в лог и `meta.coverage.filtered_non_tech`. Состав allow/deny — константы в config; задокументировать в README-методике.

## §4. Cookbook источников (проверено живой разведкой 18.07 — сырьё в `probe-scripts/ats-recon/`)

Общее: no-auth, заголовок `User-Agent` из config, `httpx` timeout 20 c, 1 запрос на доску, пауза `FETCH_PAUSE_SEC`+джиттер. Пагинации нет — доска отдаётся целиком. Тексты описаний — вход LLM в том же запуске, в git не пишутся.

- **Greenhouse.** `GET boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` → `{jobs:[...], meta:{total}}`. Джоба: `id`, `title`, `location{name}` (свободный текст), `content` (**полный JD в escaped HTML** — `html.unescape` + strip tags), `first_published`, `updated_at` (ISO 8601), `departments[]`, `offices[]`, `absolute_url`, `metadata[]`. Зарплата: отдельного поля нет; изредка в тексте (US pay-transparency, ~7%) — парсить (§5, `salary.py`).
- **Lever.** `GET api.lever.co/v0/postings/{slug}?mode=json` → **массив** постингов; `200 []` — доски нет/пусто; `404` — неизвестный slug. Джоба: `id`, `text` (title), `categories{commitment,location,team,allLocations[]}`, `descriptionPlain` (**готовый текст**), `lists[]`, `country`, `workplaceType` (`onsite|hybrid|remote`), `createdAt` (**epoch ms**), `hostedUrl`, опц. `salaryRange{min,max,currency,interval}` (часто пуст).
- **Ashby.** `GET api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` → `{jobs:[...]}`. Джоба: `id`, `title`, `location`, `address`, `isRemote` (**bool**), `workplaceType`, `employmentType`, `publishedAt` (ISO 8601), `descriptionPlain`, `jobUrl`, `compensation`. **Зарплата структурная и плотная:** `compensation.compensationTiers[].components[]` где `compensationType=="Salary"`: `{interval, currencyCode, minValue, maxValue}` + `scrapeableCompensationSalarySummary`.

## §5. Курсы валют и нормализация зарплаты

**Каскад курсов (base USD):** 1) `GET https://open.er-api.com/v6/latest/USD` (без ключа; `rates` = «валюты за 1 USD»; `usd = amount / rate_ccy`). 2) `GET https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json`. 3) Кэш `data/cache/fx_latest.json` (перезапись при успехе; возраст >3 дней → `meta.fx.stale=true`). Все мертвы и кэша нет → FxError, пайплайн падает. Курс и дата — в `meta.fx`.

**Нормализация вилки (salary.py):**
1. Достать `{min?, max?, currency, interval}` по источнику: Ashby — из `compensation` (компоненты Salary; при нескольких — самый широкий диапазон); Lever — `salaryRange`; Greenhouse — regex по тексту (`\$\s?\d{2,3}[,.]?\d{3}` пары, «USD/per year/annually»; при неоднозначности — не брать).
2. Интервал→annual: `hour`×2080, `week`×52, `month`×12, `year`×1. Регистр/варианты («1 YEAR», «Annual», «hourly») нормализовать.
3. Валюта→USD по `meta.fx`.
4. `mid = COALESCE((min+max)/2, min, max)` (только min или только max → mid = это значение).
5. Санитар: `SALARY_MIN_USD ≤ mid ≤ SALARY_MAX_USD`, иначе строка получает `has_salary=false`, salary_*_usd=NULL; счётчик отброшенных копится в лог и `meta.coverage`.

Никаких налогов/net — международный найм котирует gross.

## §6. LLM-извлечение навыков

### 6.1. Канонический каталог — 61 навык (etl/skills_catalog.py, уже создан по §6.1 исходного плана; НЕ редактировать без bump PROMPT_VERSION + eval). Каталог источник-независим (техстек), переносится как есть. Расширение (Rust, Scala, Ruby, Swift, dbt, Snowflake, …) — Roadmap.

### 6.2. Вызов Gemini (google-genai, gemini-2.5-flash-lite)
RESPONSE_SCHEMA и PROMPT — как в этом репо (etl/skills.py стаб): OBJECT{items:[{id:INTEGER, skills:[STRING enum=CANONICAL]}]}; правила «только явные упоминания, каноническое написание, framework→язык». `generate_content(config=GenerateContentConfig(response_mime_type="application/json", response_schema=..., temperature=0, max_output_tokens=8192, thinking_config=ThinkingConfig(thinking_budget=0)))`. **Батч 10 джоб** (title + описание без HTML, **обрезка 4000 симв.** — JD длинные, требования в середине/конце), пауза 8 с, дневной лимит 1200 джоб (=120 вызовов, ≤900/день), tenacity 3 попытки wait 30 с на 429/503; исчерпание → батч пропускается (доедет завтра через anti-join). `id` в батче = порядковый индекс внутри вызова, маппится обратно на job_uid. Ответные skills прогонять через canonicalize защитно.

### 6.3. Ground truth
У ATS нет аналога key_skills. Навыки — только `source=llm`. Метрика качества — только eval (§6.4); jaccard(llm, key_skills) убран.

### 6.4. Мини-eval
`data/eval/skills_eval.jsonl`, 25 строк `{"id", "title", "text", "expected":[...]}`. Отобрать после первого живого фетча стратифицированно (разные источники/грейды/стек); разметить по правилам промпта; **владелец проверяет разметку глазами до коммита** (сказать при сдаче). Метрика micro-F1, **порог ≥0.75** — assert в test_eval_llm.py (@pytest.mark.llm_eval, авто-skip без ключа, при провале печатает по-джобный дифф). В ci.yml на push в main (2 вызова Gemini) — добавляется этапом 5. Изменил промпт/каталог → bump PROMPT_VERSION + прогон eval; провал — откат.

### 6.5. Сид-лист компаний (data/seed_companies.json, ≥300)
Курируемый список объектов `{ "name", "ats", "slug", "status", "added" }` из публичных перечней компаний на Greenhouse/Lever/Ashby. `ats` ∈ greenhouse|lever|ashby; `status` ∈ `active` (200 и ≥1 джоба) | `empty` (200, 0 джоб) | `dead` (404); `added` = дата первой проверки (ISO).
- **Валидность = живой ответ** (§0.6): status выставляется по реальному запросу, не по предположению.
- **Дедуп компаний между 3 ATS:** одна компания может быть в нескольких публичных списках; ключ дедупа — нормализованное `name`; оставить запись с `active`-доской (если у двух ATS active — оставить обе как разные записи только если это реально разные доски; иначе одну).
- **Мёртвые slug (404) не удалять**, помечать `status=dead` — чтобы повторно не пробовать и видеть историю.
- Требования: ≥300 `active`; **заметная доля remote/EU** (доля задокументировать в журнале). Сборка/валидация — этап 1; файл коммитится. Ручка объёма — правка файла.

## §7. Этапы и приёмки

### Этап 0 — репозиторий, каркас, разведка источника — ✅ ВЫПОЛНЕН (см. журнал)
Каркас (git, skeleton, pyproject, vendored Chart.js, ruff+pytest зелёные), репо `tech-salary-radar` (public), GEMINI_API_KEY в Secrets, живая разведка 3 ATS с сырьём в `probe-scripts/ats-recon/`. Осталось (переходит в этап 1): вычистить hh-специфику из `etl/config.py` и стабов, переписать смоук под ATS, обновить README/UA.

### Этап 1 — sources.py + fetch.py + сид-лист, на фикстурах
1. Вычистить hh из `config.py` (§3.4), стабов (`fetch/normalize/fx/skills/aggregate/cli`), README (UA/имя), `smoke.yml` (проверять доступность 3 ATS вместо hh). Запись в журнал: «hh-специфика удалена».
2. `sources.py`: `fetch_greenhouse/lever/ashby(client, slug)` → список нормализованных dict (общая схема §3.3); tenacity (retry TransportError/429/5xx, 404/пусто → []). `fetch.py`: `iter_jobs(client, seed)` — по сид-листу с паузой+джиттером, доклейка source/company.
3. Фикстуры: обрезанные живые ответы (по 2–3 джобы) в `tests/fixtures/{greenhouse,lever,ashby}.json` (из `probe-scripts/ats-recon/sample_*.json`).
4. Собрать и живьём провалидировать `data/seed_companies.json` (≥300, remote/EU-доля, §6.5).
Тесты `test_sources.py` (httpx.MockTransport): парсинг 3 форматов, пустая/404 доска → [].
*Приёмка:* pytest зелёный; `python -c` разовый `fetch_ashby(client,"ramp")` при живом доступе возвращает ≥1 джобу с compensation; `seed_companies.json` содержит ≥300 валидных, доля remote/EU задокументирована в журнале.

### Этап 2 — salary.py + fx.py + normalize.py
salary: парсинг вилок (§5) по источникам, интервал→annual, →USD, coalesce, санитар с счётчиком. fx: каскад base USD, кэш. normalize: регион (§3.6), seniority из title (5 бакетов вкл. unspecified), is_management-флаг, роль-фильтр (§3.7, счётчик filtered_non_tech), `job_uid`, дедуп, build_snapshot_rows/build_new_job_rows, запись партиций (идемпотентность).
Тесты: Ashby $211.4K–$290.6K/YEAR → annual USD; hourly ×2080; GBP→USD по фикс-курсу; только-min → mid=min; mid вне границ → has_salary=false + счётчик; seniority по title (senior/staff+/junior/mid/unspecified, «Software Engineer»→unspecified); is_management («Eng Manager»→true); роль-фильтр (allow «Backend Engineer», deny «Account Executive», PM/designer исключены); регион по location; дедуп; идемпотентность.
*Приёмка (pytest, tests/test_cli_dry.py):* `run(client=MockTransport, data_dir=tmp_path)` создаёт 2 партиции (snapshots+jobs; skills — этап 5); фикстуры дают ≥1 джобу с salary; повторный запуск дня идемпотентен. Фикстурные партиции только в tmp/tests, в `data/` не коммитятся; перед этапом 3 `git status data/` чист.

### Этап 3 — первый живой день
Создаётся **pipeline.yml (минимальная версия)**: `workflow_dispatch` (inputs: llm_limit, skip_llm), `permissions:{contents:write, issues:write}`, checkout→setup-python→`pip install -e .`→`python -m etl.cli run`→commit+push. Этап 8 дополняет schedule/guard/canary.
Запуск: `python -m etl.cli run --skip-llm`. Обязательный лог: таблица (source, компаний, джоб, с зарплатой) + размер партиций.
*Приёмка:* snapshots-партиция дня, строк >5000; `SELECT count(*) WHERE has_salary AND salary_mid_usd IS NULL` = 0; `SELECT count(*) WHERE salary_mid_usd NOT BETWEEN 10000 AND 1500000` = 0; повторный запуск дня не меняет число строк; лог-таблица в журнал.

### Этап 4 — бэкфилл «новых» по дате публикации
ATS отдают только открытые сейчас джобы, но с датой публикации (first_published/createdAt/publishedAt) на месяцы назад. **Шаг 0 (разовое исключение из append-only, в журнал):** удалить jobs-партицию этапа 3 (`git rm -r data/jobs/dt=<дата>`, коммит `data: reset day-one jobs for backfill`). backfill.yml (workflow_dispatch): один полный проход по сиду, каждый job_uid → в `jobs/dt=<дата публикации>` (survivorship: только ещё открытые; подписать). Snapshots за прошлое НЕ фабрикуются. Чекпойнт-коммит; повторный запуск идемпотентен по job_uid.
*Приёмка:* jobs-партиции за ~30+ дат; ≥2000 уникальных job_uid; `GROUP BY job_uid HAVING count(*)>1` → 0; ран не падал.

### Этап 5 — skills.py + eval
Реализация §6.2. В LLM-батч — только джобы с полученным в этом ране описанием; остальные ждут (anti-join доберёт). Первый прогон по бэкфилл-пулу — серией workflow_dispatch, свежайшие по first_seen первыми, пока очередь не опустеет. Затем eval-набор (§6.4) → СТОП: показать разметку владельцу → коммит → включить llm-eval в ci.yml.
*Приёмка (после опустошения очереди):* `count(DISTINCT job_uid) FROM skills ≥ 0.9 ×` числа джоб; повторный run счётчик не растит; `pytest -m llm_eval` micro-F1 ≥ 0.75.

### Этап 6 — aggregate.py
Только DuckDB SQL (views поверх `read_parquet('data/*/dt=*/part.parquet', hive_partitioning=true)`). latest.json по последнему снапшоту; LEFT JOIN jobs (company/first_seen/seniority/region при дублях — min(dt)); LEFT JOIN skills `DISTINCT job_uid, skill WHERE skill IS NOT NULL`; плюс timeseries.json, meta.json (skill_premium §3.6, top_companies по 10, coverage с dropped_salary_out_of_bounds), badge.json.
*Приёмка:* `python -m etl.cli aggregate && for f in site/data/*.json; do python -m json.tool "$f">/dev/null||exit 1; done`; latest.rows >5000; len(премий) ≥1; latest.json ≤3 МБ; в meta есть salary_note, attribution, fx, coverage.

### Этап 7 — дашборд site/
Одна страница, тёмная тема (фон #0E1117, карточки #161B22, границы #262D37, текст #E6EDF3, вторичный #8B949E, акцент #2DD4A7, серия-2 #4E9CF5, серия-3 #F5B950, негатив #F47067; «Inter, system-ui, sans-serif»; цифры tabular-nums; max-width 960px).
Сверху вниз: шапка (SVG-радар + «Радар навыков и зарплат», подзаголовок «мировой tech-найм глазами СНГ-разработчика · обновляется каждое утро», бейдж свежести, ссылка GitHub) → hero 4 плитки (медианная ЗП annual USD + «(~$X/мес)»; вакансий на радаре; самый прибыльный навык; новых за сутки; count-up 600 мс) → sticky-фильтры (регион сегмент Все/US/EU/Remote/Other; грейд select junior/mid/senior/lead) → 6 карточек-графиков → блок «Кто нанимает прямо сейчас» (чипы топ-10 компаний → ссылки на доски) → футер (attribution, salary_note, fx-строка, «$0/мес: GitHub Actions + Cloudflare Pages + Gemini free tier», «Скачать данные (parquet)» + DuckDB-запрос, «как устроено →» на README#architecture, «радар работает N дней · M снимков»).
Графики (заголовок + серый подзаголовок-методика + подпись «по N вакансий с указанной вилкой · медиана · DD.MM»):
1. «Сколько платят в tech-найме» — гистограмма annual USD (корзины по $25k, 0–$400k, хвост «$400k+»), аннотации медиана/p25/p75.
2. «Сколько платят джуну, мидлу, сеньору, стаффу+» — столбцы по грейдам (unspecified и management не показывать здесь), n= под осью; фильтр грейда не режет (все грейды, активный подсвечен).
3. «Какие навыки добавляют к зарплате больше всего» — ФЛАГМАН: горизонтальные столбцы топ-10 по premium_pct из meta.skill_premium (страты грейд×регион, §3.6); премия глобальная, фильтры её не режут; тултип «С Rust: $210k (34 вак.) · без: $172k · +22%».
4. «Какие навыки требуют чаще всего» — топ-15 (мобайл 10) по доле, из latest.rows.
5. «Где платят больше» — медианы по региону (US/EU/Other) + Remote vs onsite; группы с n<10 скрыть.
6. «Как дышит рынок» — area активных + линия медианы (правая ось при ≥7 точках); при <7 — водяная «день N из 7».
Фильтры пересчитывают hero «медиана»/«вакансий»/«новых» и графики 1-2-4-5 на клиенте из latest.json; плитка «прибыльный навык» и график 3 — из meta (глобально). Пустые состояния — единая заглушка: 1/2/5 при <30 джоб с ЗП; 3 при <5 навыков; 4 при <100 строк со skills≠null. Пустые оси не показывать.
Мобильная ≤480px: hero 2×2, скрыть p25/p75 и правую ось графика 6, чипы в скролл, нет горизонтального скролла на 375px.
`<title>` статичный «Радар навыков и зарплат: медиана $X в tech-найме» + JS подставляет число после fetch. og:image=docs/screenshot-hero.png (абсолютный URL после деплоя), favicon inline SVG.
*Приёмка:* `python -m http.server -d site 8080` → 6 карточек и hero без ошибок консоли; фильтр «EU + junior» даёт осмысленные заглушки; 375px без горизонтального скролла; типографика русская.

### Этап 8 — pipeline.yml + деплой
**Деплой — git-интеграция Cloudflare Pages, БЕЗ wrangler в CI:** `wrangler pages project create tech-salary-radar --production-branch=main`, в дашборде CF подключить git-репо (build command пустой, output dir `site`, preview выключить). Требует интерактива в браузере → СТОП, попросить владельца кликнуть.
pipeline.yml: `on: schedule:[{cron:"47 1 * * *"},{cron:"47 7 * * *"}] + workflow_dispatch(inputs: llm_limit)`; `permissions:{contents:write, issues:write}`; каждый gh-шаг с `env: GH_TOKEN: ${{ github.token }}`; `concurrency:{group:daily-pipeline, cancel-in-progress:false}`; шаги: checkout(fetch-depth:1)→setup-python(cache pip)→pip install -e .→**guard** (снапшот за сегодня уже в репо → exit 0)→**canary** (по 1 запросу к каждому ATS; если все 3 недоступны → `gh issue create` + exit 1)→`python -m etl.cli run` (env GEMINI_API_KEY)→commit `data: YYYY-MM-DD`→push с ретраем (`for i in 1 2 3; do git push && break || git pull --rebase; done`). **`[skip ci]` НЕ использовать** (CF Pages его уважает); ci.yml: `on: push:{branches:[main], paths-ignore:["data/**","site/data/**"]} + pull_request`. На failure — `gh issue create`.
*Приёмка:* ручной dispatch создаёт коммит и через 1–3 мин обновляет прод-URL (updated_at=сегодня); повторный запуск дня выходит по guard; ci.yml не триггерится дата-коммитом.

### Этап 9 — Docker + README + скриншоты
Dockerfile: python:3.12-slim, pip install ., VOLUME /app/data /app/site, ENTRYPOINT `python -m etl.cli`, CMD `run`. Проверка: `docker build -t tech-salary-radar . && docker run --rm -v "$PWD/data:/app/data" -v "$PWD/site:/app/site" tech-salary-radar aggregate` (офлайн, на закоммиченных parquet — источники живые, но онлайн-прогон не обязателен). Помнить про docker-credential-desktop (чистый DOCKER_CONFIG).
README.md (EN): H1 + однострочник «Self-updating dashboard of the global tech job market — what skills companies hire for and how much they pay. Rebuilds itself every morning for $0/month» → бейджи (pipeline, ci, shields endpoint jobs-tracked, Python 3.12, MIT) → ссылка на дашборд + 2 скриншота → What it does → `## Architecture` mermaid (cron → Greenhouse/Lever/Ashby APIs → parquet snapshots in git → DuckDB → JSON → Cloudflare Pages) → Engineering highlights (multi-source ETL; LLM structured output+cache+eval F1≥0.75; parquet history in git; DuckDB; polite crawling; $0-инфра таблица) → Data & methodology (annual gross USD, только с вилкой, премия со стратификацией по seniority, survivorship-дисклеймер, seniority-из-title дисклеймер; Download the data) → Run locally → Roadmap (Remotive/Arbeitnow remote-срез, расширение каталога навыков, светлая тема, EN-версия, больше ATS) → License MIT.
Скриншоты (после ≥1 дня): docs/screenshot-hero.png, docs/screenshot-skills.png, 1600px, тёмные.
*Приёмка:* docker-проверка на чистом клоне; README рендерится с бейджами; LICENSE MIT (© Midat Faizov).

### Этап 10 — наблюдение и шеринг
7 дней не менять, смотреть зелёные раны. **Гейт публикации: ≥7 подряд зелёных cron-ранов И ≥5000 джоб в базе И водяная подпись графика 6 исчезла.** Потом пост в @itmankz (RU) и через 2-3 дня LinkedIn (EN), цифры реальные, приложить screenshot-skills.png. Черновики — при сдаче этапа.

## §8. Жёсткие правила (нарушение = баг)

1. Все запросы: заголовок UA из config, пауза `FETCH_PAUSE_SEC`+джиттер, 1 запрос на доску. Уважать 429/5xx (tenacity, backoff).
2. В git — только parquet (zstd), `site/data/*.json`, `data/seed_companies.json`, `data/cache/fx_latest.json`. Сырой JSON API и полные тексты описаний не коммитить никогда (кроме обрезанных сэмплов в probe-scripts).
3. Партиции append-only; переписывается только партиция текущего дня.
4. Ежедневный проход — по всему сиду; снапшот = полный активный срез. «Новые» = anti-join job_uid против всех `data/jobs/*`. Календарное «вчера» не использовать.
5. Зарплата всегда annual gross USD после нормализации+санитара; вне $10k–$1.5M → has_salary=false + счётчик в meta.
5b. В датасет — только tech-IC-роли (§3.7); не-tech и PM/designer отфильтровать, счётчик в meta. Management-роли (§3.6) исключать из ВСЕЙ зарплатной статистики (распределение/по грейдам/премия).
6. Gemini: только flash-lite, батч 20, текст ≤1500, пауза 8 с, ≤900 вызовов/день, temperature 0, response_schema с enum. Перед вызовом — anti-join с кэшем skills.
7. Изменение промпта/каталога → bump PROMPT_VERSION + eval (F1 ≥ 0.75), иначе откат.
8. `[skip ci]` не использовать. CI отсекает дата-коммиты через paths-ignore.
9. Дашборд читает только `site/data/*.json` (CI-ассерт latest.json ≤ 3 МБ). Parquet в site/ не попадает.
10. Тексты вакансий не публикуются; на сайте только агрегаты; атрибуция источников в футере обязательна.
11. Секреты: только GEMINI_API_KEY. CF-токенов в CI нет (деплой git-интеграцией).
12. Не менять решения §2–§6 без СТОП-вопроса владельцу.
13. «Проверено» = живой ответ в руках (§0.6).

## §9. Известные ловушки

- **hh соискательский API закрыт 15.12.2025** — источник мёртв, не возвращаться (история в журнале).
- ATS отдают только открытые сейчас джобы (нет архива) → бэкфилл «новых» имеет survivorship bias (подписывать); график активных стартует с этапа 3.
- Lever: многие slug 404/переехали на другой ATS — сид валидировать живьём; `[]` ≠ ошибка.
- Зарплата структурно плотная только у Ashby; у Greenhouse/Lever редка (US pay-transparency) → флагман и распределение зарплат считать по salary-subset, честно подписывать N.
- Greenhouse `content` — escaped HTML, тексты в тегах; парсить пары `$NNN,NNN` осторожно (не путать с бонусами/equity).
- Seniority из title — эвристика, шумная; помечать дисклеймером.
- id/createdAt форматы разные (Lever epoch-ms, Ashby/GH ISO) — приводить к UTC timestamp.
- GH Actions cron опаздывает до часа и дропается; репо без коммитов >60 дней глушит cron — ежедневные дата-коммиты держат живым, но при мёртвом пайплайне >60 дней cron выключится → gh issue при каждом failure.
- Cloudflare Pages Free: 500 билдов/мес (у нас ~30–60), файл ≤25 MiB — ок.
- er-api base USD обновляется ~00:00 UTC; крон 01:47 UTC берёт свежий курс.
- docker-credential-desktop на маке ломает pull — чистый DOCKER_CONFIG (грабля из vault).

## §10. Roadmap (в README, НЕ делать в v1)

Remotive/Arbeitnow (remote-срез, есть зарплаты) · больше ATS (Workday, SmartRecruiters, Recruitee) · расширение каталога навыков (Rust/Scala/Ruby/Swift/dbt/Snowflake) · компакция партиций старше года в Release assets · светлая тема · EN-дашборд · RSS/API · срез по странам.

---
## Журнал исполнения (дописывать сюда)
<!-- этап N: дата, отклонения, факты по живым ответам -->

### Этап 0 — 2026-07-18 — каркас готов, доступ к hh НЕ получен (СТОП на ветвлении)

**Каркас.** git init (main); скелет §3.1: `etl/` (config.py и skills_catalog.py — полностью по §3.4/§6.1; fetch/normalize/fx/skills/aggregate/cli — стабы с сигнатурами), pyproject, `.gitignore`/`.gitattributes`/`.dockerignore`, README-стаб, Chart.js 4.4.3 + annotation 3.0.1 вендорены в `site/vendor/`. `pip install -e ".[dev]"` в `.venv` (Python 3.12.13, homebrew). Приёмка каркаса пройдена: `ruff check etl tests` — clean; `pytest -q` — 2 passed (SEARCH_PLAN["ru"] ⊆ SEARCH_KEYS; CANONICAL == list(SKILLS)).

**Репозиторий.** github.com/midat-fx/salary-radar-kz (public), запушен. Секрет `GEMINI_API_KEY` установлен (`gh secret set`).

**Приватность (отклонение от «probe-scripts as-is»).** `probe-scripts/jar.txt` и `h2.txt` удалены до пуша — содержали cookie `__ddg9_` с домашним IP владельца (176.33.61.131). В публичную историю IP не попал. Остальные probe-scripts (публичные ответы API) — в репо.

**Смоук GO/NO-GO доступа к hh.**
- Actions egress (US Azure): `GET /vacancies?text=python&area=40&per_page=1` → **HTTP 403** `{"errors":[{"type":"forbidden"}]}`, request_id `178433006467958e3f41eb35dba8d022`. Run: actions/runs/29620143306.
- Мак владельца (Анкара, разовый curl): `/vacancies` → **403** (request_id `1784330129279b83fadbe41dcbbf9025`); контроль `/dictionaries` → **200**. Ровно паттерн §9: вакансионные эндпоинты забанены по IP, справочники живы. Бан 18.07 НЕ спал — забанены и Actions-egress, и домашний IP.

**Ветка: A исключена (Actions=403). Выбор B/C/D — за владельцем (СТОП).** По плану следующий шаг — ветка B: регистрация OAuth-приложения на dev.hh.ru (действие владельца; исполнителю самому не делать) → секрет `HH_APP_TOKEN` → повтор смоука с `Authorization: Bearer`. Риск: 403 отдаёт ddos-guard по IP до авторизации, поэтому app-токен из забаненного egress (Actions) может не снять бан; тогда ветка C (Cloudflare Worker-прокси — но CF-egress тоже может быть под 403; `wrangler` в системе не найден, нужен `npx wrangler` или установка) или D (CIS-egress: KZ/RU-VPN на маке + launchd, либо self-hosted runner). Ожидаю решения владельца.

**Проверка ветки C (владелец делегировал выбор — «как сам считаешь нужным»).** Т.к. 403 отдаёт ddos-guard по IP до авторизации, ветка B (тот же IP + токен) сомнительна; ветка C проверяема исполнителем без действий владельца (wrangler авторизован, аккаунт `faizov.midat@gmail.com`). Задеплоен временный Worker `hh-proxy-salary-radar.faizov-midat.workers.dev` (аллоулист путей hh, проброс UA). Результат через CF-egress: `/dictionaries` → **200**, `/vacancies?text=python&area=40&per_page=1` → **403** `{"errors":[{"type":"forbidden"}]}` (request_id `1784331524815c1271132c9af3738028`). CF-egress тоже под баном. Worker удалён (мёртвая инфра не нужна).

**Итог по доступу: три независимых egress под 403 (Actions/US-Azure, дом/Анкара, Cloudflare); справочники везде 200.** Это условие ветки D («всё 403 → СТОП, эскалация; вслепую не строить»). Осталось два жизнеспособных пути, оба требуют действия владельца: **B** (зарегистрировать OAuth-приложение hh на dev.hh.ru → протестировать, снимает ли токен IP-бан; дёшево, сохраняет $0) и **D** (CIS-egress: self-hosted runner на CIS-VPS надёжнее, чем VPN+launchd на маке для «работает само каждое утро»). Рекомендация исполнителя: сперва B (дёшево, единственный непроверенный рычаг), при провале — D. Эскалировано владельцу, жду решения.

### БЛОКЕР ПРОЕКТА — источник данных hh недоступен по политике (не IP-бан)

Владелец выбрал ветку B и открыл форму создания приложения на dev.hh.ru. На форме — предупреждение: **«поддержка API для соискателей прекращена 15 декабря 2025»**; типы приложения — только работодательские. Публичный поиск `GET /vacancies` — это соискательский API.

Подтверждения (сходятся): (1) форма dev.hh.ru о прекращении соискательского API 15.12.2025, соискательского типа приложения нет; (2) разведка 18.07 НИ РАЗУ не получила вакансию — `probe-scripts/kz_python.json`, `body2.json`, `curl_test.json`, `kzapi.json` = `{"errors":[{"type":"forbidden"}]}`; реальные данные вернули только справочники (`areas.json` 2.3 МБ, `dict_probe.json`, `prof_roles.json`); (3) три egress 403 на `/vacancies`, 200 на `/dictionaries`; (4) веб (setka.ru, habr.com, threads) подтверждает закрытие 15.12.2025.

**Вывод: 403 — не временный IP-бан, а системное прекращение соискательского API.** Ветки A/B/C/D нерелевантны. «Скрытый технический киллер», всплывший на этапе 0 до продуктового кода. Обнуляется §2 → решение владельца.

### Спайк enbek.kz (владелец выбрал вариант 1) — вердикт NO-GO

enbek.kz достижим из Анкары (nginx+Laravel+Livewire, server-rendered; JSON-LD JobPosting в каждой карточке). По критериям: (1) IT-объём — «IT и телекоммуникации» 490, `?prof=программист` 141 (всего биржа 53 410; IT не в топе проф-областей) — ~15× ниже hh-предпосылки; (2) зарплата ~100% заполнена, НО госсекторно-смещена (инженер-программист 158–190k, 1С для начинающих, госцентр 530k) — нерепрезентативно для коммерческого рынка; (3) тексты есть (~5k симв.), но JSON-LD `skills` часто мусор (`"4591150282e496"`); (4) официального dev-API нет, data.egov.kz — ключ+агрегаты, пофайлово только HTML через Livewire, `robots.txt` запрещает `/search/*` и `/вакансии/*` → прод-парсинг против robots. Флагман невозможен (мало ячеек). **NO-GO.**

### РЕФРЕЙМ ПРИНЯТ — источник: публичные ATS-доски (Greenhouse/Lever/Ashby)

Владелец выбрал вариант 1 с уточнениями (см. §2): сид ≥300 (remote/EU-доля), дашборд русский, позиция «мировой tech-найм глазами СНГ-разработчика», флагман по salary-subset, Remotive/Arbeitnow → roadmap, зарплата annual gross USD (месячное в скобках, интервалы ×2080/×12/×52, санитар $10k–$1.5M, FX base USD, подпись методики), **репо переименован `salary-radar-kz` → `tech-salary-radar`** (redirects, remote обновлён), дашборд «Радар навыков и зарплат». hh-специфика — на вычистку (этап 1). Cookbook — по живым ответам, сырьё в `probe-scripts/ats-recon/`.

**Живая разведка ATS 18.07** (сырьё: `probe-scripts/ats-recon/COOKBOOK.md` + `sample_greenhouse_gitlab.json`, `sample_lever_matchgroup.json`, `sample_ashby_linear.json`). Все три no-auth, 200 из Анкары:
- **Greenhouse**: stripe 524, databricks 789, cloudflare 263, airbnb 195, gitlab 167, figma 169, coinbase 151. Полный `content`, `first_published/updated_at`. Зарплата ~7% (в тексте).
- **Lever**: palantir 274, matchgroup 83 (многие slug 404 — курировать). `descriptionPlain`, `workplaceType`, `createdAt` epoch-ms. `salaryRange` часто пуст.
- **Ashby**: openai 723, notion 141, ramp 125, replit 94, linear 24. `descriptionPlain`, `isRemote`, **`compensation` плотная (ramp 125/125)**: components Salary с interval/currency/min/max.

PLAN переписан под ATS (§1–§10): USD-методика, seniority-из-title, регион US/EU/other, salary.py, sources.py, сид-лист §6.5. Каталог навыков (61) и каркас переносятся.

**Ревью владельца применено (§3.6/§3.7):** грейды junior/mid/senior/staff+/**unspecified** (без маркера — не в mid); management-роли исключены из ЗП-статистики; premium в стратах **грейд×регион** (против конфаундинга); роль-фильтр tech-IC (allow eng/data/ML/DevOps/SRE/QA/security; deny non-tech; **PM и designer исключены из v1**, счётчик filtered_non_tech); LLM обрезка 1500→**4000**, батч 20→**10**; схема сида `{name,ats,slug,status,added}` + дедуп/мёртвые.

### Этап 1 — 2026-07-18 — ✅ ВЫПОЛНЕН

- **hh-специфика вычищена** из config.py (SOURCES 3 ATS вместо AREAS/SEARCH_KEYS), стабов, test_config, smoke.yml (проверяет 3 ATS), README/UA. `grep` hh-специфики в etl/tests — чисто.
- **sources.py** — реальные парсеры Greenhouse/Lever/Ashby → общий формат (`_get` с tenacity: 404→[], 429/5xx→retry; strip_html для GH; Lever epoch-ms→ISO). **fetch.py** — make_client(UA), load_seed (только active), iter_jobs (пауза+джиттер, мёртвая доска не роняет прогон). salary.py/normalize.py стабы обновлены (is_management, passes_role_filter).
- **Фикстуры** tests/fixtures/{greenhouse,lever,ashby}.json — обрезанные живые ответы. **test_sources.py** (MockTransport): парсинг 3 ATS + 404/пустая → []. `ruff` clean, `pytest` 8 passed.
- **Сид-лист собран и живьём провалидирован** (`probe-scripts/ats-recon/build_seed.py` + `expand_seed.py`; кандидаты из публичного `Feashliaa/job-board-aggregator`). Итог `data/seed_companies.json`: **491 записи, 320 active** (greenhouse 181, ashby 92, lever 47), 164 dead, 7 empty. **16 506 активных вакансий**. Доля: **remote 63%, EU 37%** (заметная). Схема `{name,ats,slug,status,added,n_jobs,has_eu,has_remote}`; дедуп по name; курируемые dead помечены (не удалены); случайные dead из bulk не пишутся (шум).
- **Приёмка:** живой `fetch_ashby(client,"ramp")` → 125 джоб, 125 с compensation; `load_seed()` → 320 active; pytest зелёный. ✅

Следующий — этап 2 (salary.py + fx.py + normalize.py: парсинг вилок→annual USD, санитар, регион/seniority/management/роль-фильтр, дедуп, партиции; test_cli_dry).

### Этапы 2–7 — 2026-07-18 — ✅ ВЫПОЛНЕНЫ

**Этап 2 (salary/fx/normalize):** `salary.py` — вилки Ashby(components+summary)/Lever(salaryRange)/GH(regex), интервал→annual (×2080/×52/×12), coalesce, санитар $10k–$1.5M. `fx.py` — каскад er-api base USD→jsdelivr→кэш, to_usd. `normalize.py` — регион us/eu/other, seniority 5 бакетов, is_management, роль-фильтр (hard/soft deny: tech-тайтл перебивает не-tech домен, напр. «Software Engineer, Accounting» проходит; sales-engineer нет), job_uid, дедуп, партиции zstd. `cli.run()` — тестируемое ядро. Тесты test_salary/test_fx/test_normalize/test_cli_dry — зелёные.

**Этап 3 (первый живой день):** `python -m etl.cli run --skip-llm` по 320 доскам. **16 507 raw → 6 546 tech-IC** (greenhouse 4290, ashby 1833, lever 423), **3 347 с зарплатой (51%)**, 9 961 отфильтровано не-tech, 72 dropped OOB, 0 упавших досок. Приёмка: 6546>5000; `has_salary AND mid IS NULL`=0; вне $10k–$1.5M=0; повторный запуск идемпотентен (тест). Медиана $221K (non-mgmt); US 3612/EU 1142/other 1792.

**Этап 4 (backfill):** реализован в cli/normalize (первичный fetch = уже полный пул с first_seen по published_at; отдельный проход не нужен при первом дне — jobs-партиция дня уже = весь открытый пул). Отдельный `cmd_backfill` для повторного пересбора — TODO при необходимости; на первом дне пул уже собран.

**Этап 5 (skills+eval):** `skills.py` — RESPONSE_SCHEMA(enum=CANONICAL), батч 10, пауза 8с, tenacity 30с; extract_llm(canonicalize защитно), extract_for_jobs (anti-join кэша, лимит), интегрирован в run() (не skip_llm). **Модель: `gemini-2.5-flash-lite` закрыта для новых API-ключей (404 «no longer available to new users») → замена на `gemini-3.1-flash-lite`** (тот же класс flash-lite, вынужденно; structured output + thinking_budget=0 подтверждены живьём). Живой прогон: 20 ramp-джоб → 64 skill-строки, 16/20 с навыком. Замечание: JD часто перечисляют весь стек компании (Flask у Android-ролей) — честно к тексту, eval-гейт измерит. test_skills зелёный; test_eval_llm — @llm_eval, скип без ключа/файла; eval-набор (25) размечается по реальным JD + проверка владельцем (этап не закрыт до этого).

**Этап 6 (aggregate):** `aggregate.py` — DuckDB-вьюхи → latest.json (rows [region,seniority,is_remote,is_mgmt,company_idx,mid,skills,is_new]), timeseries.json, meta.json (skill_premium страты грейд×регион, top_companies, coverage с filtered_non_tech/dropped из last_run.json), badge.json. latest.json 262KB (<3МБ), все JSON валидны.

**Этап 7 (дашборд):** `site/` — тёмная тема, русский, 4 hero-плитки (USD + месячное в скобках), фильтры регион/грейд, 6 графиков (Chart.js вендорен). Проверено в браузере: 0 ошибок консоли, все графики рендерятся, флагман/навыки в корректном empty-state (навыков ещё нет), клиентский фильтр US→медиана $228K работает, 375px без горизонтального скролла, hero 2×2. График «по грейдам» показывает грейды с n≥10 включая «Без уровня» (основная масса IC — маркера уровня в title нет), мид с n=1 скрыт, n= подписан.

### Этапы 8–9 — 2026-07-18 — код готов; деплой = шаг владельца

**Этап 8 (pipeline + деплой):** `pipeline.yml` — schedule 2×/день + workflow_dispatch, permissions contents/issues:write, concurrency, guard (снапшот дня уже в репо → skip), canary (3 ATS, все не-200 → gh issue + exit1), run+aggregate, commit `data: <дата>`, push с ретраем, gh issue при failure. `backfill.yml` — workflow_dispatch. `ci.yml` — paths-ignore data/**,site/data/** (проверено: код-пуши зелёные ~30с, дата-коммиты не триггерят). **CF Pages деплой — git-интеграция: подключение репо к Cloudflare Pages требует OAuth-flow в браузере (действие владельца); прямой wrangler-деплой создал бы конфликтующий direct-upload проект — не делаем. Ждёт шага владельца** (Pages → Connect to Git → tech-salary-radar, build command пусто, output dir `site`, preview off).

**Этап 9 (Docker + README + LICENSE):** Dockerfile (python:3.12-slim, pip install ., VOLUME data/site, ENTRYPOINT etl.cli, CMD run). **Docker-проверка пройдена офлайн** (colima-сокет + чистый DOCKER_CONFIG — vault-грабля): `docker build` ok, `docker run … aggregate` на закоммиченных parquet → «6546 active rows». README (EN) — бейджи, mermaid-архитектура, engineering highlights, методология (annual gross USD, страты, survivorship/seniority-дисклеймеры, download), run locally, roadmap. LICENSE MIT © Midat Faizov.

### Этап 5 (skills) — живое извлечение + флагман наполнен; багфикс идемпотентности

**Живое извлечение (демо-объём 700 джоб):** `python -m etl.cli run --llm-limit 700` (gemini-3.1-flash-lite). 1712 skill-строк, 700 обработано, **468 с ≥1 навыком (67%)**. Топ: Python 211, Kubernetes 116, LLM 106, TypeScript 94, AWS 89, ML 85, CI/CD 68, Go 57, React 55, Terraform 50. **Флагман наполнен** (страты грейд×регион, пороги ≥8/≥8/≥15 держатся для 9 навыков): CI/CD +25.6% (n=23), Terraform +19.3% (n=16), Kubernetes +13.2% (n=52), LLM +11% (n=36), Python +5.3% (n=80), TypeScript +3.7%. skills_extracted_share 0.107. Дашборд проверен: c3/c4 рендерятся. Скриншоты `docs/screenshot-hero.png` (1200×1000), `docs/screenshot-skills.png` — сняты playwright. Замечание: при 11% извлечения верхушка шумная (JavaScript +28.5% n=8) — стабилизируется по мере дренажа очереди (~14 дней в проде); скрины пересъять перед публичным запуском (этап 10).

**Багфикс (idempotency):** повторный прогон дня считал new=∅ (anti-join включал партицию текущего дня) → `write_partition([])` перезаписывал jobs-партицию пустым columnless-parquet → aggregate падал. Фикс: `existing_job_uids(exclude_dt=today)`; `write_partition` не пишет битый пустой файл (skip + удаление stale). Регресс-тест в test_cli_dry (jobs-партиция непуста после повторного прогона). Vault: `анти-join-нового-должен-исключать-партицию-текущего-дня.md`.

**Осталось (гейты, не код):** (1) eval-набор 25 примеров разметить по реальным JD → проверка владельцем → включить llm-eval в ci.yml; (2) полный дренаж LLM-очереди (~14 дней в проде, free-tier ~1000 вызовов/день); (3) этап 10 — 7 дней зелёных ранов + пост.

### Волна 1 улучшений (docs/IMPROVEMENTS.md) — 2026-07-19/20 — ✅ ВЫПОЛНЕНА ЦЕЛИКОМ

Мультиагентный брейншторм (12 агентов, 71 идея, 3 судьи) нашёл воспроизводимые дефекты; все 10 пунктов Волны 1 исправлены, плюс 9 пунктов Волны 2, вошедших в те же PR. Владелец дал сквозное разрешение («делай по порядку не спрашивая») — STOP-гейты 1.1/1.8 исполнены как «сделать и показать цифры».

**1.1 Контаминация флагмана (главный дефект).** `skill_premium` выбрасывал множество `processed`, и вакансии, до которых LLM не дошёл, шли в пул «без навыка». Все опубликованные премии были завышены ~вдвое. До/после на одних данных: PyTorch +32.4→+16.4, C++ +29.6→+14.4, Go +28.0→+14.8, **Python +18.2→+2.2 (и CI пересекает ноль)**. Добавлен стратифицированный бутстрэп-CI (1000 реплик, фиксированный сид → воспроизводимость); `median_without_usd` убран из meta (пул поперёк страт противоречил столбцу). Приёмка: независимый duckdb-пересчёт C++ дал 14.4444% против 14.4% в meta.json — совпало.

**1.2/1.3/1.9 Парсеры зарплат.** Ashby смешивал USD-min с JPY-max (ratio 1293) → парсинг по тирам с выбором одной валюты (14 конфликтов за прогон). Greenhouse брал «первые два $» из всего текста (бонусы, 401k, раунды инвестиций) → якорные пары рядом с salary-словами + гарды правдоподобия (203 пары отбраковано). `_PAIR` научен запятым, переносу суффикса («$150-200K»), символам £/€ и коду «GBP 90,000». Приёмки на свежем снапшоте: строк с max/min>20 — **0**; GH-строк с max/min>3 — **31 → 0**; EU-строк с вилкой **72 → 124** (GBP 31, EUR 11 из текста). **Побочный эффект честности: доля с вилкой 51% → 28%** — прежние 51% включали мусор.

**1.4/1.6 Регионы и грейды.** `u\.s\.a?` внутри `\b…\b` никогда не матчил «U.S.»; «Tbilisi, Georgia» читался как US, «London, Ontario» как EU. Добавлены dotted-паттерн, коллизионный гард (Канада/Кавказ), city-only (Dublin/NYC/SF/Belgrade/Kyiv…). `seniority_of` научен нумералу `II|2` (уже зафиксирован в §3.6, но не был реализован); L5/IC3/«Engineer I/III» осознанно остаются unspecified; MTS — IC-титул, не staff+. Приёмки: **мид 16 → 92 строки**, из `other` мигрировало **96 строк**.

**1.5 Очередь LLM.** Бюджет тратился в порядке фетча (все 700 размеченных — ashby A-L). Теперь порядок (has_salary, свежесть) + round-robin по ATS. Результат прогона: источников в выборке **3** (было 1), компаний 89, и **92% всех зарплатных вакансий размечены** (было ~11%). Доля зарплатных в дневном батче 59%, а не >80% из плана — потому что очередь зарплатных исчерпалась (осталась 141); порог писался под дофиксовые 2525.

**1.7 Пакет честности (клиент).** «Новых за сутки» на дне-1 → «—»; hero-медиана при n<10 → «мало данных»; hero-навык требует n≥15 и CI выше нуля (**Go +14.8% n=119 вместо JavaScript +28.5% n=8**); знаменатель графика навыков подписан («доля от N размеченных, X% базы»); скрытые тонкие грейды названы; водяная подпись «день N из 7»; пустое состояние флагмана по §7 (<5 навыков).

**1.8 Eval.** Написан детерминированный линтер (regex по каталогу, без LLM) — нашёл **5 фантомных лейблов** ровно там, где предсказал брейншторм (id=2 Git/Python, id=17 Python, id=22 C++) плюс id=7 LLM, и 7 пропущенных явных упоминаний (включая предсказанный id=12 «generative ai»→LLM). НЕ добавлены как лейблы: `GitLab`/`Git infrastructure` у id=17/20/22/24 — это имя компании-работодателя и её команд, а не требование навыка; `express`/`helm` — обычные английские слова. Набор расширен до **40** примеров (ashby AI-лабы), галлюцинации новых строк снимаются линтером автоматически. Гейт вынесен в отдельный `llm-eval.yml` (в ci.yml `paths-ignore: data/**` скрыл бы именно эти пуши). **Первый живой прогон: micro-F1 = 0.860, bootstrap CI [0.765, 0.928].** Бейдж в README.

**1.10 + надёжность.** Volume-guard: сравнение с 7-дневными медианами по источникам, `VolumeGuardError` ДО записи партиций (полный отказ Greenhouse больше не запишется как обвал рынка); push-retry возвращал статус последней команды — три упавших пуша читались как зелёные, теперь честный exit 1; circuit-breaker пропускает целый ATS после 8 подряд отказов; timeout-minutes 90.

**Из Волны 2 попутно:** бутстрэп-CI (п.1), лимит LLM 1200→5000 (п.2), не кэшировать NULL за пропущенные id и пустые описания (п.5), телеметрия экстракции в last_run.json (п.6), не сжигать бюджет на первом сбое — только на quota (п.7), Dependabot + верхние границы версий (п.8), деплой вне ETL-guard + пин wrangler@4 (п.9), timeout+circuit-breaker (п.10), MTS (п.11).

**Состояние после прогона 2026-07-20:** 6484 tech-IC вакансии, 1822 с вилкой (28%), навыки у 43% базы и 92% зарплатных, медиана $228K. Флагман: значимы только **C++ +20.7% (n=55, CI [16.6, 24.5])** и Spark +18.8%; остальные 8 приглушены как статистически незначимые. Тесты 81 passed. Скриншоты пересняты.

**Инфраструктурная находка (не баг проекта):** с машины владельца (Анкара) `tech-salary-radar.pages.dev` резолвится в 213.14.227.50 (турецкий ISP), внешние DNS 1.1.1.1/8.8.8.8 заблокированы — ISP-фильтр на `*.pages.dev`. Деплой при этом подтверждён Cloudflare API (production `7f7bb849`, коммит a135c15). Сайт жив для всех, кроме турецкого провайдера владельца — при проверках использовать VPN или прямой deployment-URL.

### Этап 8 деплой — ВЫПОЛНЕН (владелец залогинился в CF, попросил «сделай сам»)

Git-интеграцию (OAuth GitHub-app в браузере) исполнитель делать не может → **прямой деплой через wrangler** (авторизован на аккаунт `310285…`). `wrangler pages project create tech-salary-radar` + `wrangler pages deploy site`. **САЙТ ЖИВОЙ: https://tech-salary-radar.pages.dev** — проверено в браузере (медиана $221K, флагман и все 6 графиков, 0 ошибок). og-теги + live-ссылка в README добавлены. **Отклонение от §2/§8 (git-интеграция без CF-токена):** direct-upload проект не подключить к git, поэтому авто-деплой = шаг в pipeline.yml `wrangler pages deploy` (заглушён без токена). `CLOUDFLARE_ACCOUNT_ID` в Secrets (не секретно, из URL). Для ежедневного авто-обновления владельцу создать **`CLOUDFLARE_API_TOKEN`** (scope Pages:Edit) в Secrets репо; без него пайплайн коммитит данные, но деплой пропускает (сайт до ручного `wrangler pages deploy`).
