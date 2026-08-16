# Architecture

`tech-salary-radar` is a daily ETL over three ATS career APIs, an LLM pass that
labels the technologies a posting asks for, DuckDB aggregation over the parquet
history, and a static dashboard on Cloudflare Pages.

## The shape of a day

```
GitHub Actions (cron)
        │
        ▼
  etl.pipeline ──► fetch ──► rates ──► normalise ──► dedupe ──► guards ──► write
        │           │         │           │            │          │         │
        │       sources/     fx/      money/ geo/    dedupe/   guards/  publish/
        │                              seniority/                        parquet
        │                              roles/  schema/
        ▼
     report ────► data/cache/last_run.json ──► etl.aggregate ──► site/data/*.json
```

The stage order carries four decisions that would be invisible as the order of
statements in a function, which is why it lives in `etl/pipeline/stages.py` with
its reasons:

- **fetch before rates** — the crawl is the long part, and fetching rates first
  would age them by its length for nothing.
- **normalise before dedupe** — the de-duplication key is built from normalised
  fields, so raw postings would compare two spellings of one city as two places.
- **dedupe before the guards** — the volume guard compares today against
  history, and comparing de-duplicated rows against non-de-duplicated ones reads
  the correction as a collapse.
- **guards before the write** — nothing is written until the day has been judged.

## Packages

| package | owns |
|---|---|
| `etl/clock.py`, `etl/rng.py` | The only two doors to ambient time and randomness. A guard test enforces it. |
| `etl/schema/` | What a stored row contains, the invariants it must satisfy, and how a day written by older code is read. |
| `etl/sources/` | One adapter per board, the shared transport with its retry, the seed and its validation, board discovery. |
| `etl/fx/` | The rate cascade, the table's own idea of how stale it is, and the conversion. |
| `etl/money/` | Pay: finding a range in text, its currency and period, whether to believe it, and what it is in annual gross USD. |
| `etl/geo/` | Region buckets, the remote reading, timezone anchoring, and the tidying that lets two boards' spellings of a city meet. |
| `etl/seniority/` | Four levels and one admission, plus the management exclusion. |
| `etl/roles/` | Whether a posting is a technical individual-contributor role at all. |
| `etl/skills/` | The catalog, the versioned prompt, the daily budget queue, the label cache, and the score that says whether a prompt change was an improvement. |
| `etl/dedupe/` | One row per job when two boards carry it. |
| `etl/guards/` | What must hold before a day joins an append-only history. |
| `etl/aggregate/` | DuckDB over the history: the day, the series, the premium and its interval. |
| `etl/publish/` | Writing parquet and JSON canonically, badges, and the revision vocabulary. |
| `etl/report/` | The fixed-order run summary. |
| `etl/pipeline/` | The run, as a context and named stages. |
| `etl/testing/` | Fakes for the five things this pipeline talks to. |

Dependencies point inward. `sources`, `money`, `geo`, `seniority`, `roles` and
`skills` depend on `schema`, `clock` and `rng`; `pipeline` depends on all of
them; nothing depends on `pipeline`.

## Three rules that shape everything else

**Nothing under `etl/` reads ambient time or randomness.** The clock, the
sleeper and the generator are ports. Every schedule in the pipeline — the crawl
pacing, the transport backoff, the LLM's rate limit, the bootstrap — is
therefore a pure function of injected values, and the suite asserts exact
numbers rather than ranges. `tests/test_determinism_guard.py` greps the package
and proves it can fail. See ADR 0007.

**Absence has two meanings and they are kept apart.** A posting the model
labelled and found nothing in stores one row with a null skill; a posting nobody
read stores no row at all. Collapsing them deflated every premium on the site
until it was found, and the distinction is carried from the parquet through the
aggregator to the browser. See ADR 0003.

**A day that looks wrong is skipped, not repaired.** There is no later run that
fixes an earlier day, so a bad one is permanent. The guards refuse before the
write; a gap in the series is the record that they did. See ADR 0005.

## Decisions

`docs/adr/` — one file each, with what it costs:

1. [Pay is annual gross USD](adr/0001-pay-is-annual-gross-usd.md)
2. [A posting contributes its midpoint](adr/0002-midpoint-not-mean.md)
3. [Unlabelled is not absent](adr/0003-unlabelled-is-not-absent.md)
4. [Premiums are measured inside a level and a region](adr/0004-stratify-by-grade-and-region.md)
5. [A day that looks wrong is skipped](adr/0005-volume-guard-refuses-the-day.md)
6. [Ambiguous levels stay unspecified](adr/0006-ambiguous-levels-stay-unspecified.md)
7. [The clock and the generator have one door each](adr/0007-clock-and-rng-have-one-door.md)
8. [Snapshots are versioned, not migrated](adr/0008-snapshots-are-versioned-not-migrated.md)
9. [The same job on two boards is one job](adr/0009-duplicates-across-boards.md)
10. [The fakes ship with the code](adr/0010-fakes-are-part-of-the-package.md)

## Tests

`tests/` mirrors `etl/`. Nothing reaches the network, nothing needs
`GEMINI_API_KEY`, and the live-model evaluation is excluded from the standard
run by its `llm_eval` marker rather than by the key being absent. Two runs of
the suite are identical, including under `TZ=Pacific/Kiritimati LC_ALL=C` and
under different `PYTHONHASHSEED` values.
