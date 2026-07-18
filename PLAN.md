# PLAN.md — «Зарплатный радар» (salary-radar-kz)

> Полная инструкция сборки. Все архитектурные решения УЖЕ приняты (4 агента-разведчика + синтез, 18.07.2026).
> Исполнитель НЕ принимает архитектурных решений — только выполняет этапы и проходит приёмки.

## §0. Правила для исполнителя

1. Работать строго по этапам §7. Этап не завершён, пока не пройдена его **приёмка**. Приёмки не пропускать и не ослаблять.
2. Встретил противоречие или невозможность — СТОП, короткий вопрос владельцу. Не изобретать обходы, особенно вокруг блокировок hh.
3. Ответы владельцу — по-русски. Код, коммиты, README — по-английски. Дашборд — по-русски.
4. Коммиты: обычные conventional (`feat:`, `fix:`, `data:`), автор только Midat Faizov <midat.faizov@gmail.com>, **без Co-Authored-By и любых упоминаний Claude/AI-ассистента**.
5. Не добавлять зависимостей сверх зафиксированных в §3.2. Не добавлять фич сверх плана — всё «хорошо бы ещё» идёт в Roadmap README.
6. Известные ловушки — §9. Прочитать ДО начала кода.
7. gh (GitHub CLI) и wrangler авторизованы у владельца; секрет GEMINI_API_KEY лежит в `~/projects/deka/.env` (строка `GEMINI_API_KEY=`) — в GitHub Secrets его добавляет исполнитель командой `gh secret set`.

## §1. Что строим и зачем

**Продукт:** публичный сайт-дашборд «Зарплатный радар» — рынок IT-вакансий Казахстана (+AI-срез России): медианные зарплаты по грейдам и городам, какие навыки требуют и **какие навыки добавляют к зарплате больше всего** (флагманский график, такого нет ни у hh, ни у калькуляторов). Обновляется сам каждое утро без участия автора. Хостинг $0/мес.

**Зачем:** флагманский Python-проект портфолио (у автора всё портфолио на TypeScript — это дыра под цель junior AI/Data Engineer). Чекбоксы: Python, pandas, SQL/DuckDB, ETL, cron-оркестрация, Docker, CI/CD, LLM structured output + eval, data quality. Вау-аудитория: рекрутеры, разработчики КЗ (@itmankz, 8k), сам автор.

**Имя:** репозиторий `salary-radar-kz` (публичный, github.com/midat-fx), на дашборде — «Зарплатный радар». Проверено 18.07: имя свободно на GitHub и в рунете.

## §2. Продуктовая рамка (зафиксировано)

- **Охват v1:** Казахстан — весь IT (11 поисковых ключей); Россия — только AI/Data-срез (2 ключа: `ml_ai`, `data`). Позиционирование: «IT-рынок Казахстана + AI-срез России». Беларусь/Узбекистан/Кыргызстан, весь IT РФ — Roadmap.
- **Валюты на дашборде:** срез KZ — тенге ₸, срез RU — рубли ₽. В данных всё нормализуется в нетто-KZT (единая аналитическая база); рублёвое отображение = KZT ÷ `rub_kzt` из meta.json. Премия навыка — в %, валюто-независима.
- **Только тёмная тема**, без переключателей языка/темы, без RSS и share-кнопок в v1.
- **Источник данных v1 — только hh.** Проверено: Adzuna не покрывает Казахстан и СНГ (страны: gb,us,at,au,be,br,ca,ch,de,es,fr,in,it,mx,nl,nz,pl,sg,za). В Roadmap: исследовать enbek.kz. Источники не выдумывать.
- Позиционирование против hh-статистики/калькуляторов (для README и постов): (1) премия навыка из полного текста через LLM — уникальный график; (2) Казахстан первым классом, в тенге; (3) открытые код+данные+методика, «не верь на слово — скачай parquet и пересчитай сам».

## §3. Архитектура

### 3.1. Дерево репозитория

```
salary-radar-kz/
├── README.md                      # EN; структура — §7 этап 9
├── PLAN.md                        # этот файл (коммитится — журнал решений)
├── pyproject.toml
├── .python-version                # 3.12
├── .gitignore                     # __pycache__/ .venv/ *.egg-info/ .pytest_cache/ .ruff_cache/ probe-scripts/__pycache__/
├── .gitattributes                 # *.parquet binary / site/vendor/* linguist-vendored
├── Dockerfile
├── .dockerignore                  # data/ site/ tests/ docs/ .git/ .github/
├── .github/workflows/
│   ├── ci.yml                     # ruff + pytest; llm-eval шаг добавляется этапом 5
│   ├── smoke.yml                  # workflow_dispatch: GO/NO-GO этапа 0, остаётся как диагностика
│   ├── pipeline.yml               # ежедневный cron: ETL → commit (минимальная версия с этапа 3)
│   └── backfill.yml               # workflow_dispatch: разовый бэкфилл 35 дней
├── etl/
│   ├── __init__.py
│   ├── config.py                  # все константы (§3.4)
│   ├── fetch.py                   # httpx-клиент hh
│   ├── normalize.py               # items → строки таблиц
│   ├── fx.py                      # курсы (hh dictionaries → er-api → кэш), gross→net, KZT
│   ├── skills_catalog.py          # 60 канонических навыков + алиасы (§6.1)
│   ├── skills.py                  # key_skills + Gemini-извлечение, кэш
│   ├── aggregate.py               # DuckDB SQL → site/data/*.json + badge.json
│   └── cli.py                     # python -m etl.cli run|backfill|aggregate
├── site/
│   ├── index.html                 # дашборд, lang=ru, тёмная тема
│   ├── app.js                     # fetch data/*.json → Chart.js, клиентские фильтры
│   ├── style.css
│   ├── vendor/chart.umd.min.js            # Chart.js 4.4.3 (вендорен)
│   ├── vendor/chartjs-plugin-annotation.min.js
│   └── data/                      # артефакты aggregate (коммитятся)
│       ├── latest.json            # компактные повакансионные строки активного среза
│       ├── timeseries.json        # по дням
│       ├── meta.json              # updated_at, курсы, пороги, атрибуция
│       └── badge.json             # для shields.io endpoint-бейджей
├── data/
│   ├── snapshots/dt=YYYY-MM-DD/part.parquet   # ежедневно: ВСЕ активные найденные (тонкая)
│   ├── vacancies/dt=YYYY-MM-DD/part.parquet   # только НОВЫЕ id этого дня (полные поля)
│   ├── skills/dt=YYYY-MM-DD/part.parquet      # навыки новых id (+ это кэш LLM)
│   ├── cache/fx_latest.json                   # фолбэк курсов (коммитится)
│   └── eval/skills_eval.jsonl                 # 25 размеченных примеров (§6.4)
├── probe-scripts/                 # разведскрипты API (уже лежат в ~/projects/salary-radar-kz/probe-scripts)
├── docs/screenshot-hero.png       # этап 9
├── docs/screenshot-skills.png
└── tests/
    ├── conftest.py                # фикстуры; авто-skip llm_eval без ключа
    ├── fixtures/hh_page.json      # записанная страница поиска (этап 1)
    ├── fixtures/hh_detail.json    # записанная деталь вакансии
    ├── test_fetch.py              # пагинация/дробление на фикстурах (httpx MockTransport)
    ├── test_normalize.py
    ├── test_fx.py
    ├── test_skills.py             # canonicalize, extract_key_skills, парсинг ответа LLM
    ├── test_aggregate.py          # на синтетическом мини-parquet
    └── test_eval_llm.py           # @pytest.mark.llm_eval (реальный Gemini)
```

Вендоринг (обе ссылки проверены 18.07, 200):
```bash
curl -sSL -o site/vendor/chart.umd.min.js 'https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js'
curl -sSL -o site/vendor/chartjs-plugin-annotation.min.js 'https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js'
```

### 3.2. pyproject.toml (зафиксирован)

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "salary-radar"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "httpx>=0.27",
  "pandas>=2.2",
  "pyarrow>=17",
  "duckdb>=1.1",
  "google-genai>=1.20",
  "tenacity>=9.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "ruff>=0.5"]

[tool.setuptools]
packages = ["etl"]

[tool.pytest.ini_options]
markers = ["llm_eval: тесты с реальным вызовом Gemini (нужен GEMINI_API_KEY)"]

[tool.ruff]
line-length = 100
```

### 3.3. Модель данных: три append-only таблицы

Ежедневный прогон записывает **дневные партиции, которые никогда не переписываются** (исключение: повторный запуск того же дня перезаписывает партиции этого дня целиком — идемпотентность).

**`data/snapshots/dt=*/part.parquet`** — все активные вакансии, найденные сегодня (тонкая, ~5-8k строк/день):

| колонка | тип |
|---|---|
| vacancy_id | int64 |
| snapshot_date | date32 (= dt партиции, таймзона Asia/Almaty) |
| source_area | string: `kz`\|`ru` |
| area_id | int32 |
| salary_from, salary_to | float64, nullable (как опубликовано) |
| salary_currency | string, nullable (нормализованный: RUR→RUB, BYR→BYN) |
| salary_gross | bool, nullable |
| salary_kzt_net_from, salary_kzt_net_to | float64, nullable (§5) |
| experience | string: noExperience\|between1And3\|between3And6\|moreThan6 |
| schedule | string, nullable: fullDay\|shift\|flexible\|remote\|flyInFlyOut |
| search_key | string (первый совпавший ключ из SEARCH_KEYS по порядку) |

**`data/vacancies/dt=*/part.parquet`** — только id, впервые увиденные в этот день (полные поля, ~200-500 строк/день):
vacancy_id, first_seen (date32), title, employer, employer_id, city (area.name), area_id, published_at (timestamp UTC), snippet (requirement+responsibility, теги вырезаны), has_description (bool), плюс те же salary/experience/schedule-поля, что в snapshots.

**`data/skills/dt=*/part.parquet`** — навыки новых id (длинный формат; **одновременно кэш LLM**):
vacancy_id (int64), skill (string, nullable — **NULL = «обработано, навыков не найдено»**), source (`llm`\|`key_skills`), prompt_version (string, сейчас `v1`), extracted_at (timestamp UTC).
Множество обработанных id = `SELECT DISTINCT vacancy_id FROM read_parquet('data/skills/*/part.parquet')` — вакансия из него никогда не переизвлекается. Очередь на извлечение = anti-join vacancies − skills (самозалечивается: не успели сегодня — доедет завтра).

**Механизм «новых» (единственный, применяется везде):** новые id дня = anti-join `vacancy_id` сегодняшнего снапшота против ВСЕХ существующих `data/vacancies/*` партиций. Никаких date_from-эвристик для определения новизны.

Правила хранения: parquet `compression="zstd"`, сортировка по vacancy_id; **raw JSON и полные тексты описаний в git не попадают никогда** (description скачивается, используется как вход LLM в тот же запуск и выбрасывается); `.gitattributes`: `*.parquet binary`; в Actions checkout с `fetch-depth: 1`.
Рост: ~0.4-0.6 МБ/день ≈ 150-220 МБ/год — для GitHub ок (лимиты: рекомендация <1 ГБ, файл <100 МБ), LFS не нужен. Ручка: если партиция дня >1.5 МБ три дня подряд — сузить RU-план (одна строка конфига).

### 3.4. etl/config.py (все константы)

```python
HH_BASE = os.environ.get("HH_BASE", "https://api.hh.ru")
USER_AGENT = "salary-radar-kz/1.0 (+https://github.com/midat-fx/salary-radar-kz; midat.faizov@gmail.com)"
AREAS = {"kz": 40, "ru": 113}                      # id подтверждены живьём 18.07
SEARCH_KEYS = {  # порядок = приоритет при дедупе
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
PER_PAGE = 100; MAX_PAGES = 20; DEPTH_SPLIT_THRESHOLD = 1900
SEARCH_PAUSE_SEC = 1.0          # + джиттер 0.2-0.4 в коде
DETAIL_LIMIT = 400; DETAIL_PAUSE_SEC = 1.0
BACKFILL_DAYS = 35              # архив hh глубже недоступен (см. §9)
LLM_MODEL = "gemini-2.5-flash-lite"; LLM_BATCH_SIZE = 20; LLM_PAUSE_SEC = 8.0
LLM_DAILY_VACANCY_LIMIT = 1200  # = 60 вызовов; дневной потолок вызовов 900 не превышать
LLM_TEXT_TRIM = 1500            # символов описания на вакансию
PROMPT_VERSION = "v1"
FX_MAX_AGE_DAYS = 3
TZ = "Asia/Almaty"
```

### 3.5. Файлы для фронта (пишет aggregate.py, читает только их)

**site/data/latest.json** — активный срез (последний снапшот), компактные строки для клиентских фильтров:
```jsonc
{
  "snapshot_date": "2026-08-20",
  "cities": ["Алматы", "Астана", "Шымкент", "Москва", "Санкт-Петербург"],  // индексы для rows
  "skills": ["Python", "SQL", ...],                                          // индексы для rows
  "rows": [
    // [country, exp, city_idx|-1, is_remote, salary_mid_kzt_net|null, skills|null, is_new]
    // skills: null = id ещё НЕ обработан LLM; [] = обработан, навыков нет; [idx,...] = навыки
    // is_new: 1 если first_seen = snapshot_date
    ["kz", "between1And3", 0, 0, 650000, [0, 1, 14], 0],
    ...
  ]
}
```
Правила: country ∈ kz|ru; exp — бакет hh; city_idx — индекс в cities или -1 («другие»); города в cities: для KZ Алматы/Астана/Шымкент, для RU Москва/СПб; salary_mid_kzt_net = COALESCE((from+to)/2, from, to) по нетто-KZT, null если зарплаты нет; skill_idx — индексы в skills (DISTINCT по вакансии). Оценка размера: 3-6k строк ≈ 150-400 КБ — ок (CI-ассерт: latest.json ≤ 2 МБ).

**site/data/timeseries.json**: `[{ "date": "2026-08-01", "country": "kz", "active": 840, "new": 37, "median_kzt": 850000 }, ...]` — только реальные снапшоты.

**site/data/meta.json**:
```jsonc
{
  "updated_at": "2026-08-20T01:52:07Z",
  "days_collected": 12,
  "fx": { "date": "2026-08-20", "source": "hh-dictionaries", "stale": false, "usd_kzt": 471.2, "rub_kzt": 6.05 },
  "tax_note": "Нетто-оценка: KZT gross ×0.90 (ИПН 10%), RUB gross ×0.87 (НДФЛ 13%). Упрощение: не учтены ОПВ/ВОСМС (КЗ) и прогрессивная шкала НДФЛ (РФ).",
  "attribution": "Данные о вакансиях: HeadHunter (hh.kz, hh.ru), официальное открытое API api.hh.ru. Проект не аффилирован с HeadHunter.",
  "skill_premium": {   // серверный расчёт (§3.6), по странам
    "kz": [ { "skill": "LLM", "n": 24, "premium_pct": 42.1, "median_with_kzt": 1250000, "median_without_kzt": 880000 }, ... ],
    "ru": [ ... ]
  },
  "top_employers": { "kz": [ { "name": "Kaspi.kz", "n": 14, "hh_url": "https://hh.kz/employer/..." }, ... ], "ru": [...] },
  "coverage": { "skills_extracted_share": 0.97 }
}
```

**site/data/badge.json** (для shields.io endpoint): `{ "schemaVersion": 1, "label": "vacancies tracked", "message": "5 214", "color": "brightgreen" }` (+второй файл при желании не делать — один бейдж достаточен).

### 3.6. Методика метрик (зафиксирована)

- Зарплатная середина: `mid = COALESCE((from+to)/2, from, to)` по **нетто-KZT**. Медианы: `quantile_cont(mid, 0.5)`, только строки с mid IS NOT NULL. Отображение ₽ на фронте: `kzt / meta.fx.rub_kzt`, округление до тысяч.
- **Премия навыка (флагман), считается в aggregate.py по каждой стране отдельно:** внутри каждого experience-бакета b, где ≥8 вакансий с ЗП с навыком И ≥8 без навыка, считаем ratio_b = median_with_b / median_without_b. Вес бакета = n_with_b (вакансий с ЗП и навыком в бакете). **premium_pct = (Σ ratio_b·n_with_b / Σ n_with_b − 1)·100.** Навык допускается при ≥15 вакансиях с ЗП суммарно; показываем топ-10 положительных. В meta: n = Σ n_with_b по учтённым бакетам; median_with_kzt/median_without_kzt — пулированные медианы по объединению учтённых бакетов (только для тултипа; числа в примерах JSON иллюстративны). График премий реагирует ТОЛЬКО на фильтр страны (не на опыт/город) — оговорено подзаголовком «стратифицировано по грейдам».
- «Новые за день» = id с first_seen = дата. Активные = строки снапшота даты.
- Подписи опыта: noExperience=«Без опыта», between1And3=«1–3 года», between3And6=«3–6 лет», moreThan6=«6+ лет».

## §4. API cookbook hh (проверено разведкой 18.07, скрипты в probe-scripts/)

- База `https://api.hh.ru`, авторизация для поиска не нужна. **Обязательный заголовок каждого запроса**: `User-Agent` из config (без него — ошибка bad_user_agent).
- **Area id (живьём):** Казахстан **40**, Россия **113**, Алматы **160**, Астана **159**. `area=40` включает все города КЗ; город вакансии — в `item.area.name`.
- Поиск: `GET /vacancies?text=<query>&search_field=name&area=40&per_page=100&page=0&order_by=publication_time`. `search_field=name` — ищем только по названию (меньше шума и глубины; честная пометка в README). Операторы text: пробел=AND, OR, NOT, скобки, "точная фраза", усечение `нейросет*`.
- Пагинация: per_page max 100, page с 0; глубина выдачи ~2000 → если `found > 1900`, дробить запрос: сначала по 4 experience-бакетам, если бакет всё ещё >1900 — по временным окнам date_from/date_to (ISO 8601; поддерживают datetime; **`+` таймзоны в URL кодировать как `%2B`** — httpx с params=dict сделает сам).
- Ответ: `{found, pages, per_page, page, items[]}`. Поля item: `id` (строка!), `name`, `area{id,name}`, `salary{from,to,currency,gross}` **и новое `salary_range` — читать salary_range с фолбэком на salary, брать только записи с mode MONTH** (словари salary_range_mode: MONTH/SHIFT/HOUR подтверждены), `experience{id}`, `schedule{id}`, `employment{id}`, `published_at` (`2026-07-17T12:34:56+0300`), `employer{id,name}`, `snippet{requirement,responsibility}` (внутри `<highlighttext>` — вырезать), `professional_roles`.
- Деталь: `GET /vacancies/{id}` → + `description` (HTML → `re.sub(r"<[^>]+>", " ", html.unescape(d))`) и `key_skills: [{"name": "Python"}]`. key_skills, когда непустой — бесплатный ground truth для eval LLM.
- `GET /dictionaries` (работает даже под баном поиска): валюты — **рубль = `RUR`** (не RUB), белорусский `BYR` → нормализуем в RUB/BYN; `rate` = единиц валюты за 1 RUR (KZT 5.997 на 18.07); experience/schedule/order_by значения — как в §3.3/§3.4.
- **Рейт-лимиты: заголовков X-RateLimit/Retry-After у hh НЕТ. Санкция — молчаливый `403 {"errors":[{"type":"forbidden"}]}` по IP на эндпоинтах вакансий, длится часами** (справочники при этом работают). Отдельно существует документированная ошибка `captcha_required` с captcha_url. Правила клиента: 1 поток; пауза ≥1 с + джиттер; на 403 — backoff 60/300/900 с, максимум 3 цикла, затем graceful stop с ненулевым кодом; **через блок не молотить**.
- `api.hh.kz` — алиас того же бэкенда; канон — api.hh.ru, страна через `area`, параметр host не использовать.

## §5. Курсы валют и налоги

Каскад источников (проверены 18.07):
1. **Primary: `GET {HH_BASE}/dictionaries`** → `currency[]` с rate (единиц за 1 RUR): `kzt_per_X = rate_KZT / rate_X`. Плюс: работает даже когда поиск под 403, ноль внешних зависимостей.
2. Fallback: `https://open.er-api.com/v6/latest/KZT` (без ключа; rates = «X за 1 KZT», инвертировать).
3. Fallback 2: `https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/kzt.json`.
4. Кэш `data/cache/fx_latest.json` (перезаписывается при каждом успехе; при возрасте >3 дней — `meta.fx.stale=true`, дашборд показывает пометку). Все источники мертвы и кэша нет → FxError, пайплайн падает.

Налоги (упрощение, честно подписано в tax_note): KZT gross=true → ×0.90; RUB gross=true → ×0.87; gross∈{false,null} — как есть; прочие валюты — как есть. Порядок: gross→net в исходной валюте → конвертация в KZT → round().

## §6. LLM-извлечение навыков

### 6.1. Канонический каталог — ровно 61 навык (etl/skills_catalog.py; список исчерпывающий, НЕ редактировать)

```python
SKILLS = {
    "Python": ["python3", "питон"], "SQL": ["t-sql", "pl/sql"],
    "JavaScript": ["js", "джаваскрипт"], "TypeScript": ["ts"],
    "Java": ["джава"], "Kotlin": [], "Go": ["golang"], "C#": ["c sharp", "csharp"],
    "C++": ["cpp"], "PHP": [], "1C": ["1с", "1с:предприятие", "1с предприятие", "1c:enterprise"],
    "Bash": ["shell", "shell scripting"],
    "pandas": [], "PyTorch": ["torch"], "TensorFlow": ["keras"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "Machine Learning": ["ml", "машинное обучение", "deep learning", "глубокое обучение"],
    "Computer Vision": ["cv", "компьютерное зрение", "opencv"],
    "NLP": ["natural language processing", "обработка естественного языка"],
    "LLM": ["genai", "generative ai", "large language models", "генеративный ии"],
    "RAG": ["retrieval augmented generation"],
    "LangChain": ["langgraph"], "MLOps": ["mlflow"],
    "Airflow": ["apache airflow"], "Spark": ["apache spark", "pyspark"],
    "Kafka": ["apache kafka"], "ClickHouse": [],
    "Power BI": ["powerbi", "power-bi"], "Tableau": [], "Excel": ["ms excel", "microsoft excel"],
    "Django": [], "FastAPI": ["fast api"], "Flask": [],
    "Spring": ["spring boot"], "Node.js": ["nodejs", "node", "express", "nestjs", "nest.js"],
    ".NET": ["dotnet", "asp.net", ".net core"], "REST API": ["rest", "restful"], "GraphQL": [],
    "React": ["reactjs", "react.js", "next.js", "nextjs"],
    "Vue": ["vuejs", "vue.js", "nuxt"], "Angular": [],
    "HTML/CSS": ["html", "css", "html5", "css3", "верстка", "вёрстка", "адаптивная верстка"],
    "Flutter": ["dart"], "React Native": ["react-native"],
    "Docker": ["docker compose", "docker-compose"], "Kubernetes": ["k8s", "helm"],
    "Linux": ["ubuntu", "unix"], "Git": ["github", "gitlab"],
    "CI/CD": ["cicd", "ci cd", "gitlab ci", "github actions", "jenkins", "teamcity"],
    "Terraform": [], "Nginx": [], "AWS": ["amazon web services"], "Grafana": ["prometheus"],
    "PostgreSQL": ["postgres"], "MySQL": [], "MongoDB": ["mongo"], "Redis": [],
    "MS SQL Server": ["ms sql", "mssql", "sql server", "microsoft sql server"],
    "Elasticsearch": ["elastic", "opensearch"],
    "n8n": [], "Selenium": ["selenium webdriver"],
}
CANONICAL = list(SKILLS)
# ALIAS_TO_CANON: casefold-словарь канонов и алиасов; canonicalize(raw) — ТОЧНОЕ совпадение, не подстрока
```
Укрупнения (Next.js→React, Nest→Node.js, Keras→TensorFlow, Prometheus→Grafana, DL→ML) — задокументировать в README-методологии.

### 6.2. Вызов Gemini (SDK google-genai, модель gemini-2.5-flash-lite)

```python
RESPONSE_SCHEMA = {
  "type": "OBJECT",
  "properties": {"items": {"type": "ARRAY", "items": {
      "type": "OBJECT",
      "properties": {"id": {"type": "INTEGER"},
                     "skills": {"type": "ARRAY", "items": {"type": "STRING", "enum": CANONICAL}}},
      "required": ["id", "skills"]}}},
  "required": ["items"],
}

PROMPT = """You label job postings with technology skills.
Input: a JSON array of postings, each {"id": int, "title": str, "text": str}, in Russian or English.
For EVERY posting return the skills from the allowed list that are EXPLICITLY mentioned in its title or text.
Rules:
- Use only skills from the allowed list, with exact canonical spelling.
- Explicit mentions only ("питон" -> Python, "верстка" -> HTML/CSS). Do not infer skills from job title level, company type, or typical stacks.
- Single allowed inference: a framework implies its language (Django/FastAPI/Flask -> also Python).
- If nothing matches, return an empty skills array for that id.
- Return every input id exactly once."""

# generate_content(config=GenerateContentConfig(response_mime_type="application/json",
#   response_schema=RESPONSE_SCHEMA, temperature=0, max_output_tokens=8192,
#   thinking_config=ThinkingConfig(thinking_budget=0)))
```

Правила: батч 20 вакансий (title + текст: description без HTML, обрезка 1500 симв.; если деталей нет — snippet); пауза 8 с между вызовами; дневной лимит 1200 вакансий (60 вызовов; жёсткий потолок 900 вызовов/день не превышать никогда); tenacity 3 попытки, wait 30 с на 429/503; исчерпание → батч пропускается (доедет завтра через anti-join). Ответный skills прогонять через canonicalize защитно; id, отсутствующие в ответе, не пишутся (останутся в очереди).

### 6.3. Ground truth бесплатно
Для вакансий, у которых hh отдал непустой key_skills, писать обе строки source=key_skills (канонизированные) и source=llm — при агрегации DISTINCT(vacancy_id, skill); совпадение llm↔key_skills — это ещё и живая метрика качества (логировать jaccard в run-лог).

### 6.4. Мини-eval
`data/eval/skills_eval.jsonl`, ровно 25 строк `{"id": int, "title": str, "text": str, "expected": ["Python", ...]}`. Отобрать после первого живого фетча стратифицированно (≥2 на каждый kz-ключ); разметить по правилам промпта; **владелец обязан глазами проверить разметку до коммита** (сказать ему об этом при сдаче этапа). Метрика micro-F1 по множествам, **порог ≥0.75** — assert в tests/test_eval_llm.py (@pytest.mark.llm_eval, при провале печатает по-вакансийный дифф). Живёт в ci.yml на push в main (2 вызова Gemini), авто-skip без ключа. Изменил промпт/каталог → обнови PROMPT_VERSION и прогони eval; провал — откат.

## §7. Этапы и приёмки

### Этап 0 — репозиторий, каркас и GO/NO-GO проверка доступа к hh
1. В `~/projects/salary-radar-kz`: git init (ветка main), скелет из §3.1 (пустые модули с сигнатурами, pyproject, gitignore/gitattributes, вендоринг Chart.js), `pip install -e ".[dev]"`.
2. `gh repo create midat-fx/salary-radar-kz --public --source=. --push` + `gh secret set GEMINI_API_KEY` (значение из ~/projects/deka/.env).
3. Workflow `smoke.yml` (workflow_dispatch): `curl -s -o /dev/null -w '%{http_code}' -A "<UA из config>" "https://api.hh.ru/vacancies?text=python&area=40&per_page=1"` + печать тела при не-200. Запустить: `gh workflow run smoke.yml && gh run watch`.
4. Параллельно проверить с Мака владельца: `python3 probe-scripts/retry_ban.py` (бан 18.07 мог уже спасть).

**ВЕТВЛЕНИЕ (зафиксировано, не изобретать другого):**
- **A. Actions → 200:** основной путь. Весь ETL (инкремент и бэкфилл) живёт в Actions. Локальная разработка — на фикстурах.
- **B. Actions → 403:** зарегистрировать приложение на dev.hh.ru НЕ пытаться самостоятельно — это действие владельца; СТОП и спросить. С app-токеном (`Authorization: Bearer`) повторить смоук; работает → секрет HH_APP_TOKEN, клиент шлёт заголовок при наличии env.
- **C. B недоступна/не помогла:** Cloudflare Worker-прокси на аккаунте владельца (код 8 строк: fetch("https://api.hh.ru"+path+search) с пробросом UA; wrangler авторизован) + `HH_BASE=https://<proxy>.workers.dev` в pipeline env. Проверить смоуком через прокси. Внимание: IP Cloudflare тоже могут быть под 403 — если так, ветка D.
- **D. Всё 403:** сбор только с CIS-egress. СТОП, эскалация владельцу (варианты: KZ/RU VPN на маке + launchd, self-hosted runner). Вслепую не строить.

В скелет включить один тест `tests/test_config.py`: импорт etl.config и etl.skills_catalog, `assert set(SEARCH_PLAN["ru"]) <= set(SEARCH_KEYS)`, `assert CANONICAL == list(SKILLS)` — иначе pytest на нуле тестов выходит кодом 5 и приёмка/CI красные.
*Приёмка этапа 0:* repo на GitHub, `ruff check etl tests && pytest -q` зелёные (≥1 тест), смоук выполнен, выбранная ветка зафиксирована строкой в PLAN.md-журнале (дописать в конец файла: дата, ветка, код ответа).

### Этап 1 — fetch.py на фикстурах
Реализовать клиент (§4): make_client (base_url=HH_BASE, UA, timeout 20 c), `_get_json` с tenacity (retry: TransportError/429/5xx, wait_exponential до 60 с, 5 попыток; 403 → CaptchaError без ретрая), search_page, search_all (пагинация ≤20 стр., дробление по experience при found>1900, при бакете>1900 — деление окна date_from/date_to пополам, пауза SEARCH_PAUSE_SEC+джиттер, доклейка `_search_key`/`_source_area`), fetch_details (≤DETAIL_LIMIT, пауза, CaptchaError → вернуть частичный dict с warning, пайплайн жив).
Фикстуры: если доступ уже есть (ветка A и бан спал) — снять 1 живую страницу и 1 деталь скриптами probe-scripts (s2/s3) или прямым httpx-скриптом; если нет — сгенерировать правдоподобные фикстуры по схеме §4 и пометить TODO «заменить на живые при первом доступе».
Тесты test_fetch.py на httpx.MockTransport: пагинация склеивается; found>1900 → вызовы с experience; 403 → CaptchaError; ретрай на 500.
*Приёмка:* pytest зелёный; при живом доступе — `python -c` разовый search_page возвращает found>0.

### Этап 2 — normalize.py + fx.py
normalize: strip_tags, normalize_currency (RUR→RUB, BYR→BYN), normalize_item (+salary_range с фолбэком на salary, только mode MONTH), build_snapshot_rows / build_new_vacancy_rows (дедуп по vacancy_id, приоритет — порядок SEARCH_KEYS), запись партиций (перезапись партиции дня целиком = идемпотентность).
fx: каскад §5, gross_to_net, to_kzt, apply_fx.
Тесты: валюты (RUR-вакансия 100k gross → RUB → ×0.87 → в KZT по фиксированному курсу), NULL-зарплата, дедуп двух ключей, идемпотентность записи.
*Приёмка — выполняется pytest-тестом (tests/test_cli_dry.py):* внутренняя функция run() принимает client (httpx.Client с MockTransport на фикстурах) и data_dir (tmp_path); тест проверяет создание 3 партиций duckdb-запросом во ВРЕМЕННОЙ директории. Фикстура hh_detail.json обязана содержать непустой key_skills (иначе skills-партиции не будет). **Всё, порождённое фикстурами, живёт только в tests/ и tmp: в data/ фикстурные партиции не пишутся и не коммитятся никогда; перед этапом 3 убедиться, что `git status data/` чист.**

### Этап 3 — первый живой день (в окружении выбранной ветки!)
Здесь же создаётся **pipeline.yml в минимальной версии**: только `workflow_dispatch` (inputs: llm_limit, skip_llm), `permissions: {contents: write, issues: write}`, шаги checkout → setup-python → `pip install -e .` → `python -m etl.cli run` → commit+push. Этап 8 лишь дополняет его schedule/guard/canary/concurrency — отдельных одноразовых workflow не заводить.
Запуск: `python -m etl.cli run --skip-llm` (в Actions через `gh workflow run pipeline.yml`, если ветка A). Обязательный лог: таблица found по каждой паре (страна, ключ) + размер партиций.
*Приёмка:* snapshots-партиция дня существует, строк >500 (KZ+RU суммарно); `SELECT count(*) WHERE salary_from IS NOT NULL AND salary_currency IN ('KZT','RUB','USD','EUR') AND salary_kzt_net_from IS NULL` = 0; повторный запуск того же дня не меняет число строк; found-таблица записана в журнал PLAN.md.

### Этап 4 — бэкфилл ретро-вакансий (35 дней)
**Шаг 0 (разовое зафиксированное исключение из append-only; записать в журнал):** удалить vacancies-партицию, созданную этапом 3 (`git rm -r data/vacancies/dt=<дата-этапа-3>`, коммит `data: reset day-one vacancies for backfill`) — бэкфилл пересобирает весь пул с корректным first_seen. Snapshots не трогать.
backfill.yml (workflow_dispatch, timeout 300 мин, `permissions: {contents: write, issues: write}`): циклом по дням `published_at` от сегодня−35 до **сегодня включительно**, `date_from/date_to` по одному дню, для каждого дня — обычный набор ключей; дедуп по vacancy_id: день id = min(published_at); собранные вакансии пишутся в vacancies/dt=<этот день>; снапшоты за прошлые даты НЕ фабрикуются (снапшот = только реальное наблюдение). Чекпойнт: после каждого дня-среза — commit+push (`data: backfill <дата>`); при 403 — backoff 60/300/900, 3 цикла, graceful stop; повторный запуск продолжает с последнего закоммиченного дня.
Замечание: это даёт ретро-объёмы «новых по дням публикации» и стартовый пул для LLM; график активных стартует с этапа 3. Id из снапшота этапа 3, закрывшиеся к моменту бэкфилла, допустимо потерять (в latest.json они получат city_idx=−1).
*Приёмка:* партиции vacancies за ~30-35 дат; суммарно ≥2000 уникальных id; `SELECT vacancy_id FROM vacancies GROUP BY 1 HAVING count(*)>1` → 0 строк; ран не падал финально (позволены зафиксированные в логе graceful-паузы).

### Этап 5 — skills.py + eval
Реализация §6. **В LLM-батч попадают только вакансии, для которых в ЭТОМ ране получена деталь (description), либо деталь недоступна навсегда (404 = вакансия закрыта; тогда snippet).** Остальные остаются в очереди — anti-join доберёт. Первый прогон по бэкфилл-пулу — серией ежедневных workflow_dispatch (детали ≤DETAIL_LIMIT=400/день, свежайшие по first_seen первыми), пока очередь не опустеет: при пуле 2-5k это 5-12 дней; идёт параллельно этапам 6-9, не блокирует их. Затем собрать eval-набор (§6.4) → СТОП: показать владельцу разметку на проверку → закоммитить → **только теперь** включить llm-eval шаг в ci.yml (до этого ci.yml не передаёт GEMINI_API_KEY и не вызывает `pytest -m llm_eval`).
*Приёмка (проверять после опустошения очереди):* `SELECT count(DISTINCT vacancy_id) FROM skills` ≥ 0.9 × количество вакансий; повторный run не увеличивает счётчик (кэш); `pytest -m llm_eval` — micro-F1 ≥ 0.75; jaccard(llm, key_skills) в логе ≥ 0.5.

### Этап 6 — aggregate.py
Только DuckDB SQL (views поверх `read_parquet('data/*/dt=*/part.parquet', hive_partitioning=true)`). Собирает §3.5: latest.json — по последнему снапшоту; **LEFT JOIN по vacancy_id с vacancies за всю историю (берём city и first_seen; при дублях id — строка с min(dt)); LEFT JOIN skills как `SELECT DISTINCT vacancy_id, skill WHERE skill IS NOT NULL` (отдельно — множество обработанных id для skills=null|[]); id без строки в vacancies → city_idx=−1, is_new=0**; плюс timeseries.json, meta.json (включая skill_premium §3.6 и top_employers по 10 на страну), badge.json.
*Приёмка:* `python -m etl.cli aggregate && for f in site/data/*.json; do python -m json.tool "$f" > /dev/null || exit 1; done`; latest.rows >500; len(премий kz) ≥1; latest.json ≤2 МБ; в meta есть tax_note, attribution, fx.

### Этап 7 — дашборд site/
Одна страница, тёмная тема (фон #0E1117, карточки #161B22, границы #262D37, текст #E6EDF3, вторичный #8B949E, акцент #2DD4A7, серия-2 #4E9CF5, серия-3 #F5B950, негатив #F47067; шрифтовой стек "Inter, system-ui, -apple-system, sans-serif", у цифр tabular-nums; max-width 960px).
Состав сверху вниз: шапка (SVG-радар + «Зарплатный радар», подзаголовок «IT-рынок Казахстана + AI-срез России · обновляется каждое утро», бейдж свежести: зелёный «данные обновлены сегодня HH:MM», янтарный «обновление задерживается» при >36 ч; ссылка-иконка GitHub) → hero 4 плитки (медианная ЗП среза; вакансий на радаре; самый прибыльный навык «LLM +42%»; новых за сутки; count-up 600 мс) → sticky-фильтры (страна сегмент KZ|RU default KZ; опыт select; город select: KZ Все/Алматы/Астана/Шымкент/Удалёнка, RU Все/Москва/СПб/Удалёнка/Другие) → 6 карточек-графиков → блок «Кто нанимает прямо сейчас» (чипы топ-10 работодателей → ссылки на hh) → футер (attribution из meta, tax_note, fx-строка, «работает на $0/мес: GitHub Actions + Cloudflare Pages + Gemini free tier», кнопка «Скачать данные (parquet)» → details с путём и копируемым DuckDB-запросом, «как это устроено →» на README#architecture, строка «радар работает N дней · M снимков данных»).
Графики (заголовок + серый подзаголовок-методика + подпись «по N вакансиям с указанной ЗП · медиана · DD.MM»):
1. «Сколько платят айтишникам в {Казахстане | России (AI/Data)}» (заголовок динамический по фильтру страны) — гистограмма mid. KZ: корзины по 100 тыс ₸, диапазон 0–2 млн, хвост «2 млн+». RU: mid → ₽ (÷ meta.fx.rub_kzt), корзины по 50 тыс ₽, диапазон 0–1 млн, хвост «1 млн+». Линии-аннотации: медиана (акцент), p25/p75 пунктир — в валюте среза.
2. «Сколько платят без опыта, мидлу и сеньору» — столбцы по 4 бакетам, значения над столбцами, n= под осью; всегда все грейды (активный подсвечен), фильтр «опыт» его не режет.
3. «Какие навыки добавляют к зарплате больше всего» — ФЛАГМАН: горизонтальные столбцы, топ-10 по premium_pct из meta.skill_premium[страна]; реагирует только на страну; тултип «С LLM: 1 250 000 ₸ (34 вак.) · без: 880 000 ₸ · +42%».
4. «Какие навыки требуют чаще всего» — топ-15 (мобайл: топ-10) по доле вакансий, из latest.rows.
5. «Где платят больше» — медианы по городам среза + Удалёнка; города с n<10 скрыть.
6. «Как дышит рынок» — area активных + линия медианы (правая ось; появляется при ≥7 точках); реагирует только на страну; при <7 точек — водяная подпись «Радар набирает историю: день N из 7».
Фильтры пересчитывают hero-плитки «медиана»/«вакансий на радаре»/«новых за сутки» (по is_new) и графики 1-2-4-5 на клиенте из latest.json; плитка «самый прибыльный навык» — только по стране (из meta). Пустые состояния — единая заглушка (иконка + строка + прогресс): графики 1/2/5 при <30 вакансий с ЗП в срезе; график 3 при <5 навыков прошедших порог; график 4 при <100 строк со skills≠null в срезе. Пустые оси не показывать никогда.
Мобильная ≤480px: hero 2×2, скрыть p25/p75-подписи и правую ось графика 6, чипы в горизонтальный скролл, нет горизонтального скролла страницы на 375px.
`<title>`: «Зарплатный радар: медиана {X} ₸ в IT Казахстана» (подставляет aggregate в index.html? НЕТ — title статичный + JS подставляет после fetch; проще и без шаблонизации). og:image = docs/screenshot-hero.png (абсолютный URL после первого деплоя), favicon — inline SVG.
*Приёмка:* `python -m http.server -d site 8080` → все 6 карточек и hero рендерятся без ошибок консоли; фильтр «Шымкент + 6+ лет» показывает осмысленные заглушки; на 375px нет горизонтального скролла; вся типографика русская.

### Этап 8 — pipeline.yml + деплой
**Деплой — git-интеграция Cloudflare Pages, БЕЗ wrangler в CI и без CF-секретов:** владелец (или исполнитель через wrangler CLI: `wrangler pages project create salary-radar --production-branch=main`, затем в дашборде CF подключить git-репо; если подключение git требует интерактива в браузере — СТОП, попросить владельца кликнуть) — build command пустой, output dir `site`, preview-деплои выключить.
pipeline.yml: `on: schedule: [{cron: "47 1 * * *"}, {cron: "47 7 * * *"}] + workflow_dispatch(inputs: llm_limit)`; `permissions: {contents: write, issues: write}` (явный блок обнуляет неперечисленные скоупы — без issues:write умрёт алертинг); каждый шаг с gh — с `env: GH_TOKEN: ${{ github.token }}`; `concurrency: {group: daily-pipeline, cancel-in-progress: false}`; шаги: checkout (fetch-depth: 1) → setup-python (cache pip) → pip install -e . → **guard**: партиция snapshots за сегодня (Asia/Almaty) уже в репо → exit 0 → **canary**: `/vacancies?per_page=1` (при 403 → `gh issue create --title "hh blocked $(date -u +%F)"` и exit 1) → `python -m etl.cli run` (env GEMINI_API_KEY, HH_BASE если ветка C) → commit `data: YYYY-MM-DD` → push с ретраем: `for i in 1 2 3; do git push && break || git pull --rebase origin main; done`. **`[skip ci]` НЕ использовать** (Cloudflare Pages его уважает и не задеплоит сайт); вместо этого ci.yml: `on: push: {branches: [main], paths-ignore: ["data/**", "site/data/**"]}` + pull_request. На failure пайплайна — шаг `gh issue create` (хватает GITHUB_TOKEN).
*Приёмка:* ручной workflow_dispatch создаёт коммит и через 1-3 мин обновляет прод-URL Pages (updated_at на сайте = сегодня); повторный запуск в тот же день выходит по guard без коммита; ci.yml не триггерится дата-коммитом.

### Этап 9 — Docker + README + скриншоты
Dockerfile: python:3.12-slim, pip install ., VOLUME /app/data /app/site, ENTRYPOINT `python -m etl.cli`, CMD `run`. Проверка при живом доступе к hh с локального IP: `docker build -t salary-radar . && docker run --rm -v "$PWD/data:/app/data" -v "$PWD/site:/app/site" salary-radar run --skip-llm` (при ветке C добавить `-e HH_BASE=…`, при B — `-e HH_APP_TOKEN=…`). **Если hh с локального IP недоступен — проверять контейнер офлайн-командой `... salary-radar aggregate`** (работает на закоммиченных parquet) — этого достаточно, к hh с забаненного IP не ходить. Помнить про воркэраунд docker-credential-desktop владельца: чистый DOCKER_CONFIG.
README.md (EN): H1 + однострочник «Self-updating dashboard of the IT job market in Kazakhstan (+AI slice of Russia). Rebuilds itself every morning for $0/month» → бейджи (pipeline workflow, ci workflow, shields endpoint-бейдж vacancies tracked из site/data/badge.json по raw-URL, Python 3.12, MIT) → жирная ссылка на дашборд + 2 скриншота → What it does (3 пункта) → `## Architecture` с mermaid (cron → fetch hh API → parquet snapshots in git → DuckDB → JSON → Cloudflare Pages; якорь для «как это устроено») → Engineering highlights (LLM structured output + cache + eval F1≥0.75; parquet history versioned in git; DuckDB analytics; polite crawling: backoff, checkpoints; таблица $0-инфры) → Data & methodology (midpoint, только вакансии с ЗП, премия со стратификацией, survivorship-дисклеймер, «поиск по названию вакансии» дисклеймер; Download the data: путь + копируемый DuckDB-запрос по https raw) → Run locally (4 команды) → Roadmap (весь IT РФ, BY/UZ/KG, enbek.kz как второй источник, светлая тема, EN-версия) → License MIT.
Скриншоты (после ≥1 дня данных): docs/screenshot-hero.png (первый экран), docs/screenshot-skills.png (график премий), 1600px, тёмные.
*Приёмка:* docker-проверка (онлайн- или офлайн-вариант выше) проходит на чистом клоне; README рендерится с работающими бейджами; LICENSE MIT (© Midat Faizov).

### Этап 10 — наблюдение и шеринг
7 дней ничего не менять, смотреть зелёные раны (issues при сбоях чинить). **Гейт публикации: ≥7 подряд зелёных cron-ранов И ≥1000 вакансий в базе И водяная подпись графика 6 исчезла.** Потом: пост в @itmankz (черновик ниже), через 2-3 дня LinkedIn (EN, черновик ниже; приложить screenshot-skills.png, цифры подставить реальные).

@itmankz:
> Сделал бесплатный радар зарплат по IT-вакансиям Казахстана: каждое утро сам собирает свежие вакансии с hh, считает медианы по городам и грейдам и показывает, какие навыки реально добавляют к зарплате.
> Без регистрации, код и данные открыты — parquet можно скачать и пересчитать по-своему.
> → [ссылка]
> Что добавить, чтобы было полезнее?

LinkedIn:
> How much does "LLM" in your skill set add to a salary in Kazakhstan? About +40%, according to my data.
> I built Salary Radar — a self-updating dashboard of the IT job market in Kazakhstan (+AI slice of Russia). It rebuilds itself every morning and costs $0/month:
> • Python ETL over the hh.ru API, daily parquet snapshots versioned in git
> • Gemini structured output extracts skills from vacancy texts (cached + mini-eval)
> • DuckDB analytics, Chart.js dashboard on Cloudflare Pages, GitHub Actions cron
> Live (RU): [link] · Code & data: [repo]
> Feedback welcome — especially on the skill-premium methodology.

## §8. Жёсткие правила (нарушение = баг)

1. Все запросы к hh: 1 поток, пауза ≥1 с + джиттер, UA из config. Параллелизм запрещён.
2. 403/captcha: backoff 60/300/900, 3 цикла, graceful stop. Через блок не молотить. Каждый ран начинается с canary.
3. В git — только parquet (zstd) и site/data/*.json. Raw JSON ответов и полные тексты описаний не коммитить никогда.
4. Партиции append-only; переписывается только партиция текущего дня при повторном запуске.
5. Ежедневный поиск — ВСЕГДА полный, без date_from: снапшот обязан быть полным активным срезом (found>1900 решается дроблением по experience/датам, §4). «Новые» = anti-join vacancy_id против всех data/vacancies/* (§3.3). date_from используется только внутри дробления глубины и в бэкфилле. Календарное «вчера» нигде не использовать.
6. Gemini: только flash-lite, батч 20, текст ≤1500 симв., пауза 8 с, ≤900 вызовов/день, temperature 0, response_schema с enum. Перед вызовом — anti-join с кэшем skills.
7. Изменение промпта/каталога → bump PROMPT_VERSION + прогон eval (F1 ≥ 0.75), иначе откат.
8. `[skip ci]` не использовать. CI отсекает дата-коммиты через paths-ignore.
9. Дашборд читает только site/data/*.json (ассерт в CI: latest.json ≤ 2 МБ). Parquet в site/ не попадает.
10. Тексты вакансий не публикуются нигде; на сайте только агрегаты; атрибуция hh в футере обязательна.
11. Секреты: только GEMINI_API_KEY (+ HH_APP_TOKEN при ветке B). CF-токенов в CI нет (деплой git-интеграцией).
12. Не менять решения §2-§6 без СТОП-вопроса владельцу.

## §9. Известные ловушки (проверено разведкой)

- **hh банит по IP молча (403 без Retry-After) именно вакансионные эндпоинты; справочники работают.** 18.07 под баном был и домашний IP владельца (Анкара), и US-egress. Отсюда весь этап 0.
- **Архив hh ≈ 35 дней** (отдаются только активные вакансии) — бэкфилл глубже невозможен; ретро имеет survivorship bias (подписывать).
- Рубль в hh — код `RUR`; белорусский — `BYR`. Нормализовать при чтении.
- Новое поле `salary_range` рядом со старым `salary` — читать новое с фолбэком, брать только mode=MONTH.
- `+` в date_from URL-кодировать (%2B); в httpx params=dict это автоматически.
- `<highlighttext>` в snippet — вырезать до записи.
- id вакансии приходит строкой — приводить к int64.
- GH Actions cron опаздывает до часа и может дропаться; в публичном репо отключается после 60 дней без коммитов — наши ежедневные коммиты держат его живым, но при мёртвом пайплайне >60 дней cron молча выключится (двойной отказ — поэтому gh issue при каждом failure).
- Cloudflare Pages Free: 500 билдов/мес (у нас ~30-60), файл ≤25 MiB — ок.
- er-api обновляется ~00:00-00:35 UTC — крон 01:47 UTC получает свежий курс.
- Первый прогон LLM по бэкфиллу: 200-350 вызовов — внутри дня; не запускать одновременно с ci-eval.
- docker-credential-desktop на маке владельца ломает pull — чистый DOCKER_CONFIG (грабля из vault).

## §10. Roadmap (в README, НЕ делать в v1)

Весь IT РФ · BY/UZ/KG · второй источник enbek.kz · светлая тема · EN-дашборд · компакция партиций старше года в Release assets · RSS/API.

---
## Журнал исполнения (дописывать сюда)
<!-- этап N: дата, ветка A/B/C/D, found-таблица, отклонения -->
