"""Failures that mean "this row does not match what we promised to store"."""

from __future__ import annotations

__all__ = ["SchemaError", "UnknownColumn", "MissingColumn", "WrongType", "InvariantViolated"]


class SchemaError(ValueError):
    """Base for every disagreement between a row and its table specification.

    A ``ValueError`` rather than a bespoke hierarchy root: callers that do not
    care about the distinction should still catch it with the exception they
    would have used for any other malformed value.
    """


class UnknownColumn(SchemaError):
    """A row carries a column the table does not declare.

    Raised rather than ignored: a stray column is almost always a rename that
    only landed on one side, and silently dropping it turns a loud bug into a
    column of nulls discovered a month later.
    """

    def __init__(self, table: str, column: str) -> None:
        super().__init__(f"{table}: unknown column {column!r}")
        self.table, self.column = table, column


class MissingColumn(SchemaError):
    """A required column is absent from a row."""

    def __init__(self, table: str, column: str) -> None:
        super().__init__(f"{table}: missing required column {column!r}")
        self.table, self.column = table, column


class WrongType(SchemaError):
    """A value cannot be stored in its declared column type."""

    def __init__(self, table: str, column: str, value: object) -> None:
        super().__init__(f"{table}.{column}: cannot store {value!r} ({type(value).__name__})")
        self.table, self.column, self.value = table, column, value


class InvariantViolated(SchemaError):
    """A row is individually well-typed but says something that cannot be true.

    ``salary_min_usd`` above ``salary_max_usd``, ``has_salary`` with no figure
    behind it, a snapshot row dated differently from its own partition. These
    are the errors worth naming separately, because each one has produced a
    published number that was wrong rather than missing.
    """

    def __init__(self, table: str, detail: str) -> None:
        super().__init__(f"{table}: {detail}")
        self.table, self.detail = table, detail
