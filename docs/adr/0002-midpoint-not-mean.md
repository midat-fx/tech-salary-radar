# 2. A posting contributes its midpoint, never a mean

## Context

Every published figure — the market median, each skill premium, every
confidence interval — is computed over one number per posting. Getting from a
posted *band* to that number is a choice with three plausible answers, and they
disagree by enough to change what the site says.

A posting can arrive as `$150,000 - $180,000`, as `from $180,000` with no
ceiling, or as a single figure. About one in nine of the ranges that parse are
one-sided, and they skew senior: "from" appears when the employer expects to
negotiate upward.

The candidates were: the arithmetic mean of the two bounds; the low bound, on
the grounds that it is the only number actually committed to; and the midpoint
with a defined fallback for incomplete ranges.

## Decision

`COALESCE((min + max) / 2, min, max)`, in that order.

- A two-sided band contributes the middle of its bounds.
- A one-sided band contributes the bound it has. "From $180,000" is a floor the
  employer committed to; averaging it against an invented ceiling would
  manufacture precision, and dropping it would remove the most senior postings
  from every sample.
- A single figure contributes itself.

This is not a mean of a distribution — there is no distribution inside a
posting, only two endpoints of a stated band — so it is described as a midpoint
throughout the code and the site.

## Consequences

- Every posting with any pay information contributes exactly one number, and
  the samples stay as large as the parsing allows.
- One-sided floors bias their contribution *downward*: the real offer is
  somewhere above the floor. Since these postings skew senior, the published
  senior medians are conservative. Stated rather than corrected, because
  correcting it would require guessing the width of a band nobody published.
- Wide bands and narrow bands contribute equally. A band wider than four times
  its floor is refused entirely by the plausibility rules, so what remains is
  narrow enough for the midpoint to be a fair summary.
- The rule lives in one function with one test file. Changing it changes every
  number on the site, which is exactly the visibility it should have.
