# 10. The fakes ship with the code they double

## Context

Five things sit between this pipeline and the outside world: the wall clock, the
pauses it takes, three job boards, a language model, and a month of parquet on
disk. Every one of them has to be replaced in a test — the clock because a
result must not depend on which side of midnight the machine is, the pauses
because proving the retry policy took fifteen real seconds, the boards and the
model because a test must never reach the network or need a key, and the parquet
because the aggregator has nothing to read without it.

Each suite had grown its own replacements. The Ashby, Lever and Greenhouse tests
each built their own `MockTransport`. The salary tests built their own rate
table. The aggregate tests built their own parquet history by hand — and that
one is instructive: it wrote a `jobs` partition with two of twenty-one columns
and job_uids that were not `source:company:job_id`, and nothing noticed until the
schema layer landed and started checking. A double built ad hoc encodes what its
author needed that afternoon, not what the real thing does.

## Decision

The fakes live in `etl/testing/`, in the package, next to the contracts they
imitate:

- `FixedClock` and `RecordingSleeper` for the two ports.
- `board_client` — a **real** `httpx.Client` on a scripted transport, so the
  client's own headers and timeout are still under test and only the socket is
  replaced.
- `ScriptedLabeller` for the model, including the four ways it misbehaves in
  production: an empty answer, a dropped id, three failures in a row, and quota
  exhaustion with the exact message the caller matches on.
- `DatasetBuilder` for the history, producing rows that satisfy the schema, so a
  test that passes against the fake would also pass against the writer.

Nothing in `etl/testing/` imports pytest. The fakes are plain objects, which
keeps a test-only dependency out of the package's module graph and lets the same
fakes drive a script or a future integration harness.

They have their own tests. A double that silently stops recording turns every
suite that uses it green for the wrong reason.

## Consequences

- A change to a real contract breaks one fake instead of four, and it breaks
  loudly, because the fakes are exercised by their own suite.
- The distinction that ADR 0003 rests on — never labelled versus labelled and
  empty — is expressible in the fake, so tests of the premium cannot accidentally
  collapse it.
- `etl/testing/` ships in the installed package. That is the cost: about seven
  hundred lines that production never calls. It is accepted because the
  alternative — a `tests/` helper module — puts the double further from the
  contract, which is the drift this decision is about.
- The recorded board payloads stay in `tests/fixtures/`. They are data captured
  from live APIs, not code, and re-recording them is a deliberate act.
