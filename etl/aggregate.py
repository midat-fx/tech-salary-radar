"""DuckDB SQL over parquet -> site/data/*.json + badge.json (PLAN.md §3.5, §3.6, stage 6)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import duckdb

BOARD_URL = {
    "greenhouse": "https://boards.greenhouse.io/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
}
SALARY_NOTE = ("Зарплаты — gross, годовые, как принято в международном найме; в USD "
               "(не-USD → USD по дневному курсу). По N вакансий с указанной вилкой.")
ATTRIBUTION = ("Данные о вакансиях: публичные карьерные доски компаний "
               "(Greenhouse, Lever, Ashby). Проект не аффилирован с ними.")


def _con(data_dir):
    con = duckdb.connect()
    d = Path(data_dir)
    con.execute(f"CREATE VIEW snap AS SELECT * FROM read_parquet('{d}/snapshots/*/part.parquet')")
    con.execute(f"CREATE VIEW jobs AS SELECT * FROM read_parquet('{d}/jobs/*/part.parquet')")
    if any((d / "skills").rglob("*.parquet")):
        con.execute(f"CREATE VIEW sk AS SELECT * FROM read_parquet('{d}/skills/*/part.parquet')")
    else:
        con.execute("CREATE VIEW sk AS SELECT NULL::VARCHAR job_uid, NULL::VARCHAR skill WHERE false")
    return con


def _write(site_data_dir, name, obj):
    out = Path(site_data_dir) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def _skills_by_uid(con, uids):
    """{job_uid: set(skills)} for processed jobs; also the set of processed uids."""
    rows = con.execute(
        "SELECT job_uid, skill FROM sk WHERE job_uid IN (SELECT unnest(?))", [list(uids)]
    ).fetchall() if uids else []
    by, processed = {}, set()
    for uid, skill in rows:
        processed.add(uid)
        if skill is not None:
            by.setdefault(uid, set()).add(skill)
    return by, processed


def _latest(con, site_data_dir):
    latest_date = con.execute("SELECT max(snapshot_date) FROM snap").fetchone()[0]
    rows = con.execute("""
        SELECT s.job_uid, s.region, s.seniority, s.is_remote, s.is_management, s.company,
               s.salary_mid_usd, j.first_seen
        FROM snap s
        LEFT JOIN (SELECT job_uid, min(first_seen) first_seen FROM jobs GROUP BY 1) j USING(job_uid)
        WHERE s.snapshot_date = ?
    """, [latest_date]).fetchall()
    uids = [r[0] for r in rows]
    skills_by, processed = _skills_by_uid(con, uids)

    companies, comp_idx = [], {}
    skills_list, skill_idx = [], {}

    def cidx(c):
        if c not in comp_idx:
            comp_idx[c] = len(companies)
            companies.append(c)
        return comp_idx[c]

    def sidx(s):
        if s not in skill_idx:
            skill_idx[s] = len(skills_list)
            skills_list.append(s)
        return skill_idx[s]

    out_rows = []
    for uid, region, seniority, is_remote, is_mgmt, company, mid, first_seen in rows:
        if uid in processed:
            sk = sorted(skills_by.get(uid, set()))
            skills_field = [sidx(s) for s in sk]
        else:
            skills_field = None
        is_new = 1 if (first_seen is not None and str(first_seen) == str(latest_date)) else 0
        out_rows.append([region, seniority, int(bool(is_remote)), int(bool(is_mgmt)),
                         cidx(company), mid, skills_field, is_new])
    _write(site_data_dir, "latest.json",
           {"snapshot_date": str(latest_date), "companies": companies,
            "skills": skills_list, "rows": out_rows})
    return latest_date, len(rows)


def _timeseries(con, site_data_dir):
    rows = con.execute("""
        SELECT s.snapshot_date,
               count(*) AS active,
               sum(CASE WHEN j.first_seen = s.snapshot_date THEN 1 ELSE 0 END) AS new,
               median(s.salary_mid_usd) FILTER (s.has_salary AND NOT s.is_management) AS median_usd
        FROM snap s
        LEFT JOIN (SELECT job_uid, min(first_seen) first_seen FROM jobs GROUP BY 1) j USING(job_uid)
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    _write(site_data_dir, "timeseries.json",
           [{"date": str(d), "active": int(a), "new": int(n or 0),
             "median_usd": round(m) if m is not None else None} for d, a, n, m in rows])


def skill_premium(con, latest_date):
    """Skill premium stratified by seniority x region on salary-bearing non-mgmt rows (PLAN.md §3.6)."""
    rows = con.execute("""
        SELECT s.job_uid, s.seniority, s.region, s.salary_mid_usd
        FROM snap s
        WHERE s.snapshot_date = ? AND s.has_salary AND NOT s.is_management
              AND s.salary_mid_usd IS NOT NULL
    """, [latest_date]).fetchall()
    if not rows:
        return []
    uids = [r[0] for r in rows]
    skills_by, _ = _skills_by_uid(con, uids)
    strata = {}   # (seniority, region) -> list[(mid, skillset)]
    all_skills = set()
    for uid, sen, reg, mid in rows:
        sk = skills_by.get(uid, set())
        all_skills |= sk
        strata.setdefault((sen, reg), []).append((mid, sk))

    results = []
    for skill in all_skills:
        num = den = total_with = 0.0
        with_pool, without_pool = [], []
        for members in strata.values():
            w = [m for m, s in members if skill in s]
            wo = [m for m, s in members if skill not in s]
            total_with += len(w)
            if len(w) >= 8 and len(wo) >= 8:
                ratio = median(w) / median(wo)
                num += ratio * len(w)
                den += len(w)
                with_pool += w
                without_pool += wo
        if total_with >= 15 and den > 0:
            pct = (num / den - 1) * 100
            if pct > 0:
                results.append({"skill": skill, "n": int(den), "premium_pct": round(pct, 1),
                                "median_with_usd": round(median(with_pool)),
                                "median_without_usd": round(median(without_pool))})
    results.sort(key=lambda r: r["premium_pct"], reverse=True)
    return results[:10]


def _meta(con, data_dir, site_data_dir, latest_date, n_active):
    d = Path(data_dir)
    fx = {"date": None, "base": "USD", "source": "er-api", "stale": True,
          "gbp_usd": None, "eur_usd": None}
    fxp = d / "cache" / "fx_latest.json"
    if fxp.exists():
        raw = json.loads(fxp.read_text())
        rates = raw.get("rates", {})
        age = (datetime.now(timezone.utc).date() - datetime.fromisoformat(raw["date"]).date()).days
        fx.update({"date": raw["date"], "stale": age > 3,
                   "gbp_usd": round(1 / rates["GBP"], 4) if rates.get("GBP") else None,
                   "eur_usd": round(1 / rates["EUR"], 4) if rates.get("EUR") else None})

    days = con.execute("SELECT count(DISTINCT snapshot_date) FROM snap").fetchone()[0]
    comp = con.execute("SELECT count(DISTINCT company) FROM snap WHERE snapshot_date=?",
                       [latest_date]).fetchone()[0]
    src = dict(con.execute(
        "SELECT source, count(DISTINCT company) FROM snap WHERE snapshot_date=? GROUP BY 1",
        [latest_date]).fetchall())
    with_sal, total = con.execute(
        "SELECT count(*) FILTER (has_salary), count(*) FROM snap WHERE snapshot_date=?",
        [latest_date]).fetchone()
    processed = con.execute(
        "SELECT count(DISTINCT job_uid) FROM sk WHERE job_uid IN "
        "(SELECT job_uid FROM snap WHERE snapshot_date=?)", [latest_date]).fetchone()[0]
    top = con.execute("""
        SELECT company, source, count(*) n FROM snap WHERE snapshot_date=?
        GROUP BY 1,2 ORDER BY n DESC LIMIT 10
    """, [latest_date]).fetchall()

    last_run = {}
    lrp = d / "cache" / "last_run.json"
    if lrp.exists():
        last_run = json.loads(lrp.read_text())

    meta = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "days_collected": int(days), "companies_tracked": int(comp), "sources": src, "fx": fx,
        "salary_note": SALARY_NOTE, "attribution": ATTRIBUTION,
        "skill_premium": skill_premium(con, latest_date),
        "top_companies": [{"company": c, "n": int(n),
                           "url": BOARD_URL[s].format(slug=c)} for c, s, n in top],
        "coverage": {
            "salary_share": round(with_sal / total, 3) if total else 0,
            "skills_extracted_share": round(processed / total, 3) if total else 0,
            "dropped_salary_out_of_bounds": int(last_run.get("dropped_oob", 0)),
            "filtered_non_tech": int(last_run.get("filtered_non_tech", 0)),
        },
    }
    _write(site_data_dir, "meta.json", meta)
    _write(site_data_dir, "badge.json",
           {"schemaVersion": 1, "label": "jobs tracked",
            "message": f"{n_active:,}".replace(",", " "), "color": "brightgreen"})


def aggregate(data_dir, site_data_dir):
    """Build latest.json, timeseries.json, meta.json, badge.json from the parquet history."""
    con = _con(data_dir)
    latest_date, n_active = _latest(con, site_data_dir)
    _timeseries(con, site_data_dir)
    _meta(con, data_dir, site_data_dir, latest_date, n_active)
    con.close()
    print(f"aggregated: {n_active} active rows @ {latest_date} -> {site_data_dir}/")
