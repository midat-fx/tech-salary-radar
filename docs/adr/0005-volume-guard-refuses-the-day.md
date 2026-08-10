# 5. A day that looks wrong is skipped, not written

## Context

The history is append-only parquet, one partition per day, committed to git by a
cron job. There is no later run that goes back and repairs an earlier day —
that is the property that makes the history worth having, and it is also what
makes a bad day permanent.

Greenhouse is about two thirds of the crawl. An hour of 500s from it, or a
`GEMINI_API_KEY` that expired, or a seed file that failed to parse, produces a
run that finishes cleanly and writes a day showing the tech job market down by
sixty per cent. The timeseries then carries that cliff forever, every median
computed across the range is dragged by it, and no amount of correct days
afterwards removes it.

The alternative to refusing is repairing: re-run the day later and overwrite the
partition. It was rejected because it makes every historical figure provisional
— any day could be rewritten, so no chart is reproducible from a commit — and
because the repair has to be triggered by somebody noticing, which is exactly
what did not happen the first time.

## Decision

Compare the day against its own recent past, per source, and write nothing when
it does not hold up.

- A source must keep at least half its seven-day median.
- The day as a whole must keep at least three fifths of the expected total. The
  second rule catches what the first cannot: every source down by forty per
  cent, each individually inside its floor.
- Fewer than three days of history means no opinion. The launch week must not be
  blocked by a guard with nothing to compare against.

A refusal exits non-zero and prints which source and which numbers. Nothing is
written and nothing is committed, so the next morning's run simply produces that
day instead.

Separately, a set of **plausibility** checks looks at the rows that did arrive
and asks whether they still mean what yesterday's meant — the share carrying a
salary, the share landing in `other`, the share reading as `unspecified`, and
whether one board contributed everything. These only warn. A shift in any of
them is a strong signal and a weak proof, and refusing on one would mean
throwing away real data the first time the market did something unusual.

The per-source circuit breaker is the same instinct one level down: eight
consecutive failures from one ATS and the crawl stops asking it, because two
hundred requests into a service already returning 429 helps nobody.

## Consequences

- A missing day in the history means a guard fired. That is a readable signal:
  the gap is the record.
- The floors are judgement, not measurement. Set too tight they refuse real
  quiet days — a public holiday across the US does move the count — and set too
  loose they let a partial outage through. Seven days of median absorbs the
  weekday shape without absorbing a month-long trend.
- A guard cannot catch a source that is *wrong* rather than *absent*: a board
  serving stale results at full volume passes every check here. The plausibility
  warnings are the partial answer, and they are warnings precisely because they
  are not conclusive.
- Because refusal happens before the write, a refused day costs the crawl's
  requests and nothing else.
