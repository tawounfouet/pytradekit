"""Canonical execution report statuses."""

from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Provider-neutral execution facts understood by the OMS."""

    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
