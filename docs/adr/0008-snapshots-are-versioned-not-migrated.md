# 8. Snapshots are versioned, not migrated

## Context

The history is append-only parquet, one partition per day, committed to git. A
month in, it is already not homogeneous: the original-currency columns arrived
after the first week, `prompt_version` after the second. Reading the whole range
with one query works today only because DuckDB fills an absent column with NULL
— which means the behaviour is a property of the reader, not a promise of the
writer, and nobody chose it.

That matters because NULL is doing two jobs at once. In `salary_mid_usd` it
means "this posting has no salary". In `currency_original` on a 18 July
partition it means "the pipeline could not have recorded one". The aggregator
cannot tell them apart, and every statistic that treats absence as evidence gets
this wrong in the same direction.

The obvious alternative is to migrate: rewrite old partitions to the current
column set whenever the schema changes. It is also the wrong one here. Those
partitions are the repository's history — each one is a commit, dated, and the
data it holds was true on that day. Rewriting them would restate the past every
time the present changes, and would turn one field addition into a diff across
a hundred and forty files.

## Decision

Every partition records the schema version it was written with, and readers
state the version they understand. The pair decides:

- **Same version** — exact match, nothing to do.
- **Older minor** — columns added since are filled from their declared defaults,
  and the fill is *reported*, not performed silently. `fill_missing` returns the
  list of names it filled so the run report can name them.
- **Newer minor** — a partition written by a deploy that was rolled back. Extra
  columns are ignored; the shared ones still mean the same thing, which is
  exactly what a minor version promises.
- **Different major** — refused. A major change means a column that already
  existed changed meaning, and reading it with today's code would produce a
  plausible wrong number rather than an error.

Defaults are declared per column, next to its type, and a default is a value —
`prompt_version` fills as `"v1"` because an unmarked label came from the only
prompt that existed then, not as NULL.

The version history is kept in code as a changelog: a reader needs to know what
a missing column meant on a given day, and that cannot be recovered from the
parquet.

## Consequences

- Old days stay exactly as they were committed. The data commits remain
  evidence of what was true then, which is the point of keeping them.
- "Could not have known" and "does not have one" stop being the same value.
- Adding a column is a minor bump and costs nothing. Changing what a column
  means is a major bump and is loud by construction — which is the intended
  friction.
- The pipeline carries a compatibility rule it must keep honest; a column added
  without a `since` marker degrades the guarantee quietly. The field
  specification test checks that every declared version appears in the history.
- Nothing here rewrites parquet. If a partition ever does need correcting, that
  is a revision with its own record, not a migration — see ADR 0009.
