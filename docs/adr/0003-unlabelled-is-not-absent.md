# 3. A posting that was never labelled is not evidence a skill is absent

## Context

The skill premium is the site's flagship number: how much more a posting pays
when it asks for Python than when it does not. It is computed by splitting
salary-bearing postings into a with-pool and a without-pool and comparing their
medians.

Labels come from a language model reading a job description, one call per ten
postings, against a free-tier budget of roughly five thousand postings a day
and a crawl that returns six and a half thousand. On any given day a large
share of postings has not been labelled at all — and that share is not random.
The queue prefers salary-bearing and newer postings, so what goes unlabelled
skews towards older ads and ads with no salary.

The obvious implementation is `skill in job.skills`. That puts every unlabelled
posting into the without-pool, which says "this job does not need Python" about
a job nobody has read. It deflated every premium on the site, and it deflated
them unevenly: rarer skills, which have smaller with-pools, were hit hardest.

## Decision

Three states, not two, and they are distinguishable in storage:

| state | rows in the skills table | pools |
|---|---|---|
| labelled, skill found | one row per skill | with-pool |
| labelled, no skills found | **one row with a null skill** | without-pool |
| never labelled | **no rows at all** | neither |

A posting with no rows takes part in no premium. It is not evidence either way,
and treating silence as a "no" is the specific mistake this records.

The null row is what makes the middle state expressible in an append-only
parquet table with no separate "processed" list. It is also why a posting the
model *silently dropped* from a reply is deliberately not written: a null row
for it would claim the model looked, permanently.

The version of the prompt that produced a label is stored beside it, and when a
posting carries labels from several generations only the newest counts — a
premium computed across two prompts mixes two definitions of the same skill.

## Consequences

- Every premium is computed over a smaller sample than the day's crawl, and the
  site says so: coverage is published next to the number.
- Coverage rising is a real improvement in the statistic's power, not just a
  bigger denominator.
- The three-state rule has to survive every layer that touches skills — the
  cache, the aggregator, the fakes. `etl/testing`'s `JobSpec` therefore
  distinguishes `skills=None` from `skills=[]`, so a test cannot accidentally
  collapse them back into two states.
- A posting that is never labelled at all is invisible to the premium forever.
  Accepted: the queue is designed so that salary-bearing postings — the only
  ones a premium can use — are labelled first.
