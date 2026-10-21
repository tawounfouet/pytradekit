"""Execution certainty associated with an order."""

from enum import StrEnum


class ExecutionCertainty(StrEnum):
    """Whether the current execution state is confirmed or uncertain."""

    CONFIRMED = "confirmed"
    UNCERTAIN = "uncertain"
