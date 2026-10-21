"""Canonical order lifecycle states."""

from enum import StrEnum


class OrderStatus(StrEnum):
    """Canonical states of the Order aggregate."""

    CREATED = "created"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"
    REPLACED = "replaced"
