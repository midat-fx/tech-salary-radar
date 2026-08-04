# 1. Pay is one number: annual, gross, in USD

## Context

The three boards quote pay in whatever the employer typed. In a single day's
crawl that is dollars, pounds and euros; hourly, daily, monthly and yearly;
base only, base plus bonus, and uncapped OTE; two-sided bands, one-sided
floors, and single figures. Some European postings quote net.

Any statistic across that set needs a common unit. The alternatives to picking
one are worse: publishing per-currency medians splits every sample until none
of them is large enough to say anything, and publishing raw figures side by
side invites the reader to compare a monthly euro band with an annual dollar
one.

## Decision

Everything is reduced to a single number per posting: **annual, gross, USD**.

- **Annual**, using stated multipliers — 2080 hours, 260 days, 52 weeks, 12
  months. These are assumptions, not arithmetic: 2080 is a full year with no
  unpaid leave, and a contractor working 46 paid weeks earns less than it says.
- **Gross**, because that is what the overwhelming majority of these postings
  quote and because net depends on jurisdiction, filing status and benefits —
  none of which a job ad contains. A posting that quotes net is read as gross
  and is therefore understated. It is not detected.
- **USD**, converted at the snapshot day's rate from a three-source cascade.
  Only USD, GBP and EUR have rates; a figure in any other currency is excluded
  rather than approximated.

Currency is recorded with a confidence: declared in a structured field, an ISO
code in text, an unambiguous symbol, or assumed. A bare `$` resolves to USD at
*assumed* confidence, because `$` is also CAD, AUD, SGD and a dozen others.

## Consequences

- One median means something, and the strata below it stay large enough to
  bootstrap.
- The base is biased towards the US, twice over: US pay-transparency law is why
  a range is present at all in most postings, and the `$`-means-USD assumption
  systematically misreads Canadian and Australian ads upward. The README states
  this under Deliberate limits rather than burying it.
- Net-quoting postings understate. Detecting them would need a jurisdiction and
  a tax model; the pipeline has neither and pretending otherwise would be worse
  than the current, stated, bias.
- Hourly and daily contract rates enter the same distribution as salaries. That
  is a real mixing of populations, and it is why the interval is stored
  alongside the converted figure — a future task can separate them without
  re-crawling.
- Rates are the snapshot day's. Historical conversion is not attempted: see the
  Deliberate limits entry.
