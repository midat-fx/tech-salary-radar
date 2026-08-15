"""The daily run, as a context and a set of named stages.

Extracted from ``etl/cli.py`` so that the command-line layer parses arguments
and nothing else. The orchestration is worth testing on its own: the order of
the stages carries three decisions that are invisible when they are just the
order of statements in a function.
"""

from etl.pipeline.context import RunContext, build_context
from etl.pipeline.run import GuardRefused, RunOutcome, execute
from etl.pipeline.stages import STAGE_ORDER, StageResult, by_source

__all__ = [
    "STAGE_ORDER",
    "GuardRefused",
    "RunContext",
    "RunOutcome",
    "StageResult",
    "build_context",
    "by_source",
    "execute",
]
