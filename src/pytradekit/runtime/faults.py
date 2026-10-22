"""Deterministic fault injection primitives used by production qualification tests."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class FaultPoint(StrEnum):
    """Deterministic crash windows qualified across runtime and reconciliation."""

    BEFORE_INBOX_CLAIM = "before_inbox_claim"
    AFTER_INBOX_CLAIM = "after_inbox_claim"
    AFTER_FILL_PERSIST = "after_fill_persist"
    AFTER_CANONICAL_APPLY = "after_canonical_apply"
    AFTER_OUTBOX_ADD = "after_outbox_add"
    BEFORE_COMMIT = "before_commit"
    AFTER_COMMIT = "after_commit"
    BEFORE_RECONCILIATION_CAPTURE = "before_reconciliation_capture"
    AFTER_RECONCILIATION_COMPARE = "after_reconciliation_compare"
    BEFORE_RECONCILIATION_RESOLUTION = "before_reconciliation_resolution"
    AFTER_RECONCILIATION_RESOLUTION = "after_reconciliation_resolution"
    BEFORE_RECONCILIATION_VERIFY = "before_reconciliation_verify"
    AFTER_RECONCILIATION_COMPLETE = "after_reconciliation_complete"


class FaultInjector(Protocol):
    """Boundary used by runtime code to expose deterministic crash windows."""

    def hit(self, point: FaultPoint) -> None:
        """Raise or return when one named fault point is reached."""

        ...


class NullFaultInjector:
    """Production default that never injects faults."""

    def hit(self, point: FaultPoint) -> None:
        """Ignore the fault point."""

        _ = point


class InjectedRuntimeFault(RuntimeError):
    """Synthetic process failure raised only by qualification injectors."""


class OneShotFaultInjector:
    """Raise exactly once when a selected fault point is reached."""

    def __init__(self, point: FaultPoint) -> None:
        self._point = point
        self._raised = False

    def hit(self, point: FaultPoint) -> None:
        """Raise once at the configured point."""

        if point is self._point and not self._raised:
            self._raised = True
            raise InjectedRuntimeFault(f"Injected runtime fault at {point.value}.")
