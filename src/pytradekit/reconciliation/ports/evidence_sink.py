"""Consistency evidence publication boundary."""

from typing import Protocol

from pytradekit.reconciliation.domain import ReconciliationRun


class ConsistencyEvidenceSinkPort(Protocol):
    """Consume completed reconciliation evidence for admission decisions."""

    def record(self, run: ReconciliationRun) -> None: ...
