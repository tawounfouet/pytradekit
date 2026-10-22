"""Minimal recovery notification boundary."""

from typing import Protocol

from pytradekit.reconciliation.domain import ReconciliationRun


class RecoveryNotifierPort(Protocol):
    """Notify operators about material reconciliation outcomes."""

    def critical_mismatch(self, run: ReconciliationRun, *, count: int) -> None: ...
    def recovery_failed(self, run: ReconciliationRun, *, reason: str) -> None: ...
    def recovery_verified(self, run: ReconciliationRun) -> None: ...
