# 6. Ambiguous levels stay unspecified

## Context

Seniority is the axis every salary figure on the site is stratified by, and it
is read from a job title, which is the only place these boards state it.

Most titles cooperate: "Senior Backend Engineer", "Junior Developer", "Staff
Software Engineer". Two groups do not.

The first is company ladder codes — `Software Engineer, L5`, `Engineer IC3`,
`Backend Engineer E4`. These are levels, precisely defined, and the definition
is internal to one employer. L5 is senior at one company and staff at another;
IC3 is mid at one and senior at another. There is no public mapping, and the
companies that publish one change it.

The second is bare numerals that are not attached to a role noun, and ranges:
`Engineer 1 - 2`.

Mapping either group onto the ladder is available and tempting: it would move a
large share of postings out of `unspecified` and make every stratum bigger,
which makes every confidence interval narrower. That is exactly the problem —
the intervals would get narrower without the evidence getting stronger.

## Decision

Four ranked levels — junior, mid, senior, staff+ — plus `unspecified`, which is
a bucket and not a gap.

- A word marker wins over a numeral: "Senior Engineer II" is senior.
- `II` or `2` directly after a role noun is mid, and only there. A numeral
  elsewhere in a title is as likely to be a product name as a level.
- A ladder code, or two numerals, resolves to `unspecified`.
- `unspecified` has no position in the ordering. `rank()` returns `None` for it
  rather than a sentinel, so a caller cannot sort it to one end and read meaning
  into where it landed.

The reading also records *which rule* fired, so "the title said nothing" and
"the title said something we refuse to interpret" are distinguishable in the run
report even though both store the same value.

One exception is coded explicitly: "Member of Technical Staff" contains the word
*staff* and is an individual-contributor title. Without a rule for it, every AI
lab's entire engineering organisation reads as staff+.

## Consequences

- `unspecified` is large, and it is largest in Europe, where ladder codes and
  bare titles are more common than the American senior/staff wording. The site
  shows it as its own bucket rather than hiding it.
- Premiums and medians within `unspecified` mix levels, so that stratum is the
  least informative one. It is published anyway, because dropping it would
  remove most European postings from the sample entirely.
- A future task can map ladder codes per company using evidence — the code is
  stored in the title, and the title is stored. Doing it by guesswork now would
  make that task impossible to evaluate.
- The management exclusion is separate and absolute: manager, director, VP,
  head and chief titles are removed from every salary statistic rather than
  bucketed, because their pay is a different distribution and mixing it moves
  the senior median without any sample changing.
