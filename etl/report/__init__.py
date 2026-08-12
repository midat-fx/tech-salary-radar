"""The run report: a fixed-order text summary of what one day's pipeline did.

It exists because the alternatives are worse. An exit code says nothing about
a run that succeeded while labelling forty postings instead of five thousand.
A log is grep-able but its shape drifts. Reading the parquet answers questions
about the data and none about the run.

The order of the fields is a contract — see :mod:`etl.report.fields`.
"""

from etl.report.collect import RunReport, collect
from etl.report.fields import FIELD_ORDER, SECTIONS, Field, field_names, section_of
from etl.report.render import MISSING, format_value, render, render_line

__all__ = [
    "FIELD_ORDER",
    "MISSING",
    "SECTIONS",
    "Field",
    "RunReport",
    "collect",
    "field_names",
    "format_value",
    "render",
    "render_line",
    "section_of",
]
