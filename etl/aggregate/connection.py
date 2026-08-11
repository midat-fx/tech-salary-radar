"""The DuckDB views every aggregate query reads, built once per run.

Three views, and the third is the interesting one. ``snap`` and ``jobs`` always
exist — a deployment without them has never run. ``sk`` may not: skills arrive
in stage 5 and a fresh deployment has none, so the view is created empty rather
than left undefined. A missing view turns every downstream query into a crash;
an empty one lets the same SQL run and produce the honest answer, which is that
nothing is labelled yet.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["open_dataset", "has_skills", "EMPTY_SKILLS_SQL"]

#: A view with the right columns and no rows. The cast matters: DuckDB needs a
#: type for each column, and without it a join against sk fails on an empty day.
EMPTY_SKILLS_SQL = (
    "CREATE VIEW sk AS SELECT NULL::VARCHAR job_uid, NULL::VARCHAR skill, "
    "NULL::VARCHAR prompt_version WHERE false"
)


def has_skills(data_dir: str | Path) -> bool:
    return any((Path(data_dir) / "skills").rglob("*.parquet"))


def open_dataset(data_dir: str | Path):
    """A connection with ``snap``, ``jobs`` and ``sk`` defined."""
    import duckdb

    con = duckdb.connect()
    root = Path(data_dir)
    con.execute(f"CREATE VIEW snap AS SELECT * FROM read_parquet('{root}/snapshots/*/part.parquet')")
    con.execute(f"CREATE VIEW jobs AS SELECT * FROM read_parquet('{root}/jobs/*/part.parquet')")
    if has_skills(root):
        con.execute(f"CREATE VIEW sk AS SELECT * FROM read_parquet('{root}/skills/*/part.parquet')")
    else:
        con.execute(EMPTY_SKILLS_SQL)
    return con
