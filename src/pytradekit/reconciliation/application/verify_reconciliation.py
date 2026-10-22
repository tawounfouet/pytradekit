"""Fresh-evidence verification of reconciliation outcomes."""

from dataclasses import dataclass

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    BrokerSnapshot,
    InternalSnapshot,
    Mismatch,
    ReconciliationRunId,
    ReconciliationScope,
)
from pytradekit.reconciliation.ports import BrokerSnapshotPort, InternalSnapshotPort
from pytradekit.reconciliation.services import SnapshotComparator
from pytradekit.runtime.ports import ClockPort


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Fresh snapshots and remaining mismatches after resolution."""

    internal: InternalSnapshot
    broker: BrokerSnapshot
    mismatches: tuple[Mismatch, ...]


class VerifyReconciliation:
    """Capture new evidence and re-run pure comparison."""

    def __init__(
        self,
        *,
        internal_snapshots: InternalSnapshotPort,
        broker_snapshots: BrokerSnapshotPort,
        comparator: SnapshotComparator,
        clock: ClockPort,
    ) -> None:
        self._internal_snapshots = internal_snapshots
        self._broker_snapshots = broker_snapshots
        self._comparator = comparator
        self._clock = clock

    def execute(
        self,
        *,
        run_id: ReconciliationRunId,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> VerificationResult:
        internal = self._internal_snapshots.capture(account_id=account_id, scope=scope)
        broker = self._broker_snapshots.capture(account_id=account_id, scope=scope)
        mismatches = self._comparator.compare(
            run_id=run_id,
            scope=scope,
            internal=internal,
            broker=broker,
            detected_at=self._clock.now(),
        )
        return VerificationResult(
            internal=internal,
            broker=broker,
            mismatches=mismatches,
        )
