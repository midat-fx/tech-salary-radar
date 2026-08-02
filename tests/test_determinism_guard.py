"""Structural guard: ``etl/`` reaches for time and randomness through two doors only.

Every schedule and every published number in this pipeline is asserted with an
exact value — the FX staleness flag, the label timestamp, the crawl pacing, the
bootstrap confidence interval. That only holds while nothing under ``etl/``
reads the machine clock or an unseeded generator.

A ``datetime.now()`` added later would fail none of those tests. It would just
make one of them able to fail at midnight, in another timezone, or on the third
verifier run — which reads as flakiness rather than as the regression it is. So
the rule is checked directly, and this file proves the check can fail.
"""

from __future__ import annotations

import re
from pathlib import Path

ETL = Path(__file__).resolve().parent.parent / "etl"

#: The two modules allowed to touch ambient time and randomness.
DOORS = {"clock.py", "rng.py"}

FORBIDDEN: list[tuple[str, re.Pattern[str]]] = [
    ("datetime.now()", re.compile(r"\bdatetime\.now\s*\(")),
    ("date.today()", re.compile(r"\bdate\.today\s*\(")),
    ("datetime.utcnow()", re.compile(r"\butcnow\s*\(")),
    ("time.time()", re.compile(r"\btime\.time\s*\(")),
    ("time.sleep()", re.compile(r"\btime\.sleep\s*\(")),
    ("random module", re.compile(r"(?m)^\s*import\s+random\b|\brandom\.[a-z]")),
]


def _sources() -> list[tuple[str, str]]:
    """(relative path, source) for every module under etl/ that is not a door."""
    return [
        (str(p.relative_to(ETL.parent)), p.read_text(encoding="utf-8"))
        for p in sorted(ETL.rglob("*.py"))
        if p.name not in DOORS
    ]


def violations(files: list[tuple[str, str]]) -> list[str]:
    """``"<path>: <what>"`` for each forbidden call, so a failure names its own fix."""
    found = []
    for path, source in files:
        for name, pattern in FORBIDDEN:
            if pattern.search(source):
                found.append(f"{path}: {name}")
    return found


def test_the_guard_actually_read_the_package():
    """A broken path would make every assertion below pass against nothing."""
    files = _sources()
    assert len(files) >= 8
    assert any(path.endswith("aggregate.py") or "/aggregate/" in path for path, _ in files)


def test_no_ambient_time_or_randomness_outside_the_two_doors():
    assert violations(_sources()) == []


def test_the_doors_exist_and_are_the_only_exemption():
    assert (ETL / "clock.py").exists()
    assert (ETL / "rng.py").exists()
    assert DOORS == {"clock.py", "rng.py"}


def test_the_guard_is_sensitive_to_each_pattern():
    """Each sample trips exactly one rule: the patterns do not overlap or shadow."""
    samples = [
        ("etl/sample.py", "stamp = datetime.now(timezone.utc)"),
        ("etl/sample.py", "day = date.today()"),
        ("etl/sample.py", "stamp = datetime.utcnow()"),
        ("etl/sample.py", "started = time.time()"),
        ("etl/sample.py", "time.sleep(0.5)"),
        ("etl/sample.py", "import random"),
        ("etl/sample.py", "pause = random.uniform(0.2, 0.4)"),
    ]
    for sample in samples:
        assert violations([sample]), f"guard missed {sample[1]!r}"


def test_the_guard_does_not_flag_the_injected_forms():
    """The shapes the package actually uses must stay clean, or the rule is unusable."""
    clean = [
        ("etl/sample.py", "now = clock.now()\nday = clock.today(TZ)"),
        ("etl/sample.py", "sleeper.sleep(jitter.next_pause())"),
        ("etl/sample.py", "rng = bootstrap_rng()\ndraw = rng.choices(pool, k=len(pool))"),
        ("etl/sample.py", "# the clock module owns datetime-now, spelled out in prose"),
        ("etl/sample.py", "from etl.rng import SeededRng"),
    ]
    assert violations(clean) == []
