"""Fakes for the five things this pipeline talks to: the clock, the pauses, the
boards, the model, and the parquet history.

They live in the package rather than in ``tests/`` for the reason ADR 0010 sets
out: a double that drifts from the thing it doubles turns every suite using it
green for the wrong reason, and the compiler is more likely to notice the drift
when the double sits next to the contract.

Nothing here imports pytest. The fakes are plain objects, so they also work from
a script or a future integration harness.
"""

from etl.testing.catalog import QuotaExhausted, ScriptedLabeller, keyword_labeller
from etl.testing.clock import DEFAULT_NOW, FixedClock, RecordingSleeper
from etl.testing.dataset import DatasetBuilder, JobSpec, build_dataset
from etl.testing.http import RecordedBoard, board_client, board_transport, load_fixture

__all__ = [
    "DEFAULT_NOW",
    "DatasetBuilder",
    "FixedClock",
    "JobSpec",
    "QuotaExhausted",
    "RecordedBoard",
    "RecordingSleeper",
    "ScriptedLabeller",
    "board_client",
    "board_transport",
    "build_dataset",
    "keyword_labeller",
    "load_fixture",
]
