# 7. The clock and the generator have one door each

## Context

Four things in this pipeline are functions of the current instant: the snapshot
partition a run writes to, the timestamp stamped onto every LLM label, the age
that decides whether the FX cache is stale, and the `updated_at` published in
`meta.json`. Two more are functions of randomness: the jitter that keeps 320
board requests off a metronome, and the stratified bootstrap behind every
confidence interval on the site.

All six used to read ambient state at the point of use — `datetime.now()` in
four modules, `random.uniform` in the crawl, `random.Random(SEED)` inside the
aggregator. The obvious approach is to leave them there and freeze time in the
tests instead, with `freezegun` or a `monkeypatch` on `datetime`.

That breaks in a specific way. Patching a module-level `datetime` reaches only
the module you named, so a test that freezes `etl.aggregate` still gets a live
clock inside `etl.skills`; the test passes and the property it claims to check
is unprotected. And the failures that result are not reproducible failures —
they are a suite that is green until it runs at midnight, in another timezone,
or three times in a row for reference verification, where a moved number reads
as flakiness rather than as the regression it is.

## Decision

`etl/clock.py` and `etl/rng.py` are the only modules in the package that may
touch ambient time or an unseeded generator. Everything else takes a `Clock`,
a `Sleeper` or an `Rng` and asks it.

- `Clock` answers `now()` (aware, UTC) and `today(tz)` (the reporting-timezone
  calendar date a run belongs to). The two are separate because the partition
  date and the label timestamp are different questions and were being answered
  by the same call.
- `Sleeper` wraps the pause between board requests, so the crawl's politeness
  costs a test nothing and the total wait becomes a number the run report can
  print.
- `Rng` is the narrow slice actually used — `uniform` and `choices` — behind a
  seeded generator. `BOOTSTRAP_SEED` is pinned and versioned, because changing
  it moves every published interval.

`tests/test_determinism_guard.py` greps the package for the forbidden forms,
names the file and the call when it trips, and proves it can fail by running
the same check over samples of each pattern.

## Consequences

- Two runs of the suite are byte-identical, including under
  `TZ=Pacific/Kiritimati` and under different `PYTHONHASHSEED` values.
- A test can walk 320 boards without waiting, and can assert the exact pacing
  rather than that "some" pause happened.
- The rule is enforced structurally rather than by review, so adding a
  `datetime.now()` later fails a test instead of quietly adding a flake.
- The cost is a parameter on about a dozen functions and a default of
  `SystemClock()` where the call site is a script rather than a pipeline stage.
  A default hides the injection slightly; the guard is what stops that default
  from spreading back into the modules.
- Production keeps real jitter: the seeded generator is still a generator, and
  only the seed — not the schedule — is fixed.
