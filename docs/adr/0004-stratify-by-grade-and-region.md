# 4. A skill premium is measured inside a level and a region, never across

## Context

"Postings that mention Kubernetes pay 47% more" is the site's headline claim,
and computed naively it is not about Kubernetes.

Two things dominate pay in this dataset and neither is a skill. **Level**: a
staff engineer earns roughly twice a junior. **Region**: US postings pay far
above European ones, partly because they pay more and partly because US
pay-transparency law is why a range is present at all — the American sample is
both richer and better covered.

Skills are not distributed evenly across either. Kubernetes appears in senior
infrastructure postings; those skew senior and skew American. Compare the
mentions against the non-mentions across the whole day and most of what is
measured is the seniority and the country. The premium would be real, large,
and about something else.

The alternative to stratifying is regression — control for level and region as
covariates. It gives a tidier answer and needs assumptions this data cannot
support: a functional form for the relationship, and enough postings per cell to
fit it. With eight postings as the minimum viable cell, a ratio of medians is
what the sample can carry.

## Decision

Split the day's salary-bearing, non-management postings into
(seniority × region) strata. Within each stratum, compare the median of the
postings that mention a skill against the median of those that do not. Combine
the per-stratum ratios into a weighted mean, weighted by the size of the
with-pool — a stratum where forty postings ask for a skill says more than one
where nine do.

Thresholds, all of them arbitrary in the sense that a different number would
also be defensible, and all stated:

- **Eight** postings on each side for a stratum to take part. Below that a
  median is one or two people's salaries.
- **Fifteen** postings mentioning a skill in total before it is published at all.
- **Ten** skills on the page. The tail is long and thin, and a list of sixty
  invites reading rank 40 against rank 41.

Every premium carries a stratified bootstrap 95% interval. Resampling happens
*within* each stratum, so a replicate never changes the composition of the
sample — the comparison stays the same comparison. A skill whose interval spans
zero is shown with that interval rather than hidden: the honest statement is
"large but uncertain", not silence.

Management titles are excluded entirely rather than given their own stratum.
Their pay is a different distribution, and mixing it moves the senior median
without any sample changing.

## Consequences

- The published premiums are smaller than a naive computation gives, and they
  are about the skill.
- Skills concentrated in one stratum can vanish: if every posting mentioning a
  tool is senior and American, no stratum has eight on both sides and the skill
  is not published at all. That is the correct answer — there is nothing to
  compare it against — but it means absence from the list is not evidence of a
  small premium.
- The `unspecified` seniority bucket is a stratum like any other, and it is
  large (ADR 0006). Premiums inside it mix levels and are the least informative
  ones on the page.
- The interval is drawn from a pinned seed. Two aggregations of the same parquet
  produce the same interval, because one that moved would be indistinguishable
  from the data having changed.
