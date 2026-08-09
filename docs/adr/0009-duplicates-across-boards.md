# 9. The same job on two boards is one job

## Context

`job_uid` is `source:company:job_id`. It identifies a **posting**, and it is
correct at that: two adverts are two adverts. But a company that runs both
Greenhouse and Lever — and several in the seed do, usually mid-migration —
publishes each opening on both, and the pipeline has been counting each one
twice.

That shows up in the two numbers the site leads with. "Jobs tracked" is
inflated by however many companies are dual-listed. Worse, the median is
computed over postings, so a dual-listed role contributes its salary twice and
a company with many openings and two boards quietly weights the whole
distribution towards its own pay band.

There is no shared identifier between boards. What is available is the company
slug, the title, and the location. Not the description — the boards trim it
differently. Not the salary — usually present on one side only, which is
exactly the case worth detecting. Not the publish date — the boards disagree by
days.

## Decision

A second key, alongside the uid: company slug, normalised title, seniority, and
the location's place tokens. Postings sharing it are one job.

The normalisation is asymmetric on purpose. Decoration is stripped — `(Remote)`,
`m/f/d`, a team suffix in brackets — because it varies between the two copies of
one advert. Level words are **not** stripped, and `+`/`#` survive the
punctuation pass, because collapsing `Senior Engineer` into `Engineer` or `C++`
into `C` would merge two genuinely different roles. That is the one error this
must never make: merging deletes a real posting from the market, while missing a
duplicate merely leaves today's inflation in place.

Which copy represents the job is decided by information, not by board: a
posting that states a salary wins over one that does not, and only then does
the board order — Ashby, Lever, Greenhouse, by how much each states outright —
break the tie. Going by board alone would prefer an empty Ashby posting to a
Greenhouse advert whose text carries a range.

The losing copy is not discarded outright. Fields the winner has **no** value
for are filled from it — Greenhouse never sends `employment_type` and often has
no publish date, while the Lever copy of the same job has both. Nothing already
stated is ever overwritten: a disagreement between two boards is not something
this layer can resolve, and quietly preferring one side would make a published
figure depend on merge order.

## Consequences

- Jobs tracked and every median stop double-counting dual-listed companies.
  The number will fall the day this is switched on, and that fall is a
  correction rather than a market movement — the run report names it.
- A posting with no company or no title cannot be keyed and is left alone.
  Grouping on an empty key would collapse every broken posting into one.
- Two roles that genuinely differ only by something the fingerprint drops —
  same title, same city, same level, different team — merge. Accepted: they are
  usually the same requisition posted twice anyway, and the alternative is
  keying on a description the boards do not agree about.
- The report carries the duplicate share and example groups. A run where it
  moves sharply is either a board changing its slugs or this layer merging
  something it should not, and both need to be visible the next morning.
