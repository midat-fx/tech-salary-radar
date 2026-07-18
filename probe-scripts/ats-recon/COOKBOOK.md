# ATS job-board API cookbook — verified live 2026-07-18

Source pivot after hh job-seeker API was discontinued (2025-12-15). New source: public,
no-auth job-board APIs of Greenhouse / Lever / Ashby. **Every fact below was confirmed
against a live response** (trimmed 2-job samples committed alongside as `sample_*.json`).
Reachable from Ankara egress; global CDNs, no geo-block, no auth.

## Greenhouse
- Endpoint: `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`
- Detail (single): `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{id}`
- Response: `{ "jobs": [...], "meta": { "total": N } }`
- Live counts: stripe 524, airbnb 195, gitlab 167, databricks 789, coinbase 151, cloudflare 263, figma 169 (200 OK each).
- Job fields: `id`, `title`, `location{name}` (free text, e.g. "San Francisco, CA"),
  `content` (**full JD as escaped HTML** — ~3k chars stripped), `first_published`, `updated_at`,
  `departments[]`, `offices[]`, `metadata[]`, `absolute_url`, `company_name`, `requisition_id`.
- Salary: **no dedicated field**; `pay_input_ranges` was null. Pay appears in `content` text only
  for US pay-transparency roles — sparse (~39/524 ≈ 7% for stripe). Needs regex over text.
- Remote: infer from `location.name` / `offices` text (no boolean).
- "New"/recency: `first_published`, `updated_at` (ISO 8601 with offset).

## Lever
- Endpoint: `GET https://api.lever.co/v0/postings/{company}?mode=json`
- Response: **JSON array** of postings (not wrapped). `200 []` for a company with no open Lever board;
  `404` for an unknown slug.
- Live counts: palantir 274, matchgroup 83 (200). Many well-known slugs 404 / have moved ATS —
  slugs must be curated, not guessed.
- Job fields: `id`, `text` (title), `categories{commitment, location, team, allLocations[]}`,
  `descriptionPlain` (**plain text ready — no HTML parsing**), `descriptionBodyPlain`, `lists[]`
  (structured requirements/responsibilities), `additionalPlain`, `country`,
  `workplaceType` (`onsite`|`hybrid`|`remote`), `createdAt` (**epoch ms int**), `applyUrl`, `hostedUrl`.
- Salary: optional `salaryRange` field; **empty for palantir (0/274)** — populated only when the
  company enters it. Sparse.
- Remote: `workplaceType` boolean-ish enum ✓.
- "New"/recency: `createdAt` (epoch milliseconds).

## Ashby  ← salary workhorse
- Endpoint: `GET https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true`
- Response: `{ "jobs": [...], "apiVersion": ... }`
- Live counts: openai 723, notion 141, ramp 125, replit 94, linear 24 (200). Unknown/empty slug → `{"jobs":[]}`.
- Job fields: `id`, `title`, `location`, `address`, `secondaryLocations[]`, `isRemote` (**bool**),
  `workplaceType`, `employmentType` (`FullTime`…), `department`, `team`, `publishedAt` (**ISO 8601**),
  `descriptionPlain` (**plain text**), `descriptionHtml`, `applyUrl`, `jobUrl`, `compensation`.
- Salary: **`compensation` present for 125/125 ramp jobs.** Structure:
  `compensation.compensationTiers[].components[]` each with
  `{compensationType:"Salary"|"Equity"|…, interval:"1 YEAR", currencyCode:"USD", minValue, maxValue}`,
  plus `scrapeableCompensationSalarySummary` ("$211.4K - $290.6K") and `compensationTierSummary`.
  Highest-quality, structured salary of the three.
- Remote: `isRemote` bool + `workplaceType` ✓.
- "New"/recency: `publishedAt` (ISO 8601).

## Cross-source implications (for the plan rewrite)
- Volume: easily thousands of live IT roles from a curated seed of companies (7 Greenhouse cos ≈ 2,258).
- Full text: present everywhere; Lever/Ashby give ready plain text, Greenhouse needs tag-strip.
- Salary: **structured & dense only on Ashby**; Greenhouse/Lever sparse (US pay-transparency in text).
  → flagship skill-premium runs on the salary-bearing subset, labeled "по N вакансий с указанной вилкой".
- Dedup: same role can appear once per company board only (no cross-board duplicates within one ATS);
  a company uses exactly one ATS, so cross-ATS dup risk is low. Dedup key = (source, company, job id).
- No pagination needed (Greenhouse/Ashby return the full board; Lever returns full array).
- Politeness: one request per company board; small seed × once/day. No documented rate limits hit.
