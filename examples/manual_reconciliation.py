"""Provider-neutral manual reconciliation example for PyTradeKit 0.6."""

from datetime import UTC, datetime
from typing import cast

from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation import (
    BrokerSnapshot,
    InternalSnapshot,
    ReconciliationRun,
    ReconciliationRunId,
    ReconciliationScope,
    ReconciliationTrigger,
    Resolution,
    SnapshotCompleteness,
    SnapshotWatermark,
)
from pytradekit.reconciliation.application import ReconcileAccount
from pytradekit.reconciliation.domain import Mismatch
from pytradekit.reconciliation.ports import ReconciliationRepository
from pytradekit.shared import CorrelationId
from pytradekit.testing import FakeClock


class MemoryRepository:
    def __init__(self) -> None:
        self.runs: dict[ReconciliationRunId, ReconciliationRun] = {}
        self.mismatches: list[Mismatch] = []
        self.resolutions: list[Resolution] = []

    def add_run(self, run: ReconciliationRun) -> None:
        self.runs[run.id] = run

    def get_run(self, run_id: ReconciliationRunId) -> ReconciliationRun | None:
        return self.runs.get(run_id)

    def save_run(self, run: ReconciliationRun) -> None:
        self.runs[run.id] = run

    def list_active(self) -> tuple[ReconciliationRun, ...]:
        terminal = {"COMPLETED", "FAILED", "CANCELLED"}
        return tuple(
            run for run in self.runs.values() if run.status.value not in terminal
        )

    def list_stale(self, *, stale_before: datetime) -> tuple[ReconciliationRun, ...]:
        return tuple(
            run for run in self.list_active() if run.started_at < stale_before
        )

    def add_mismatch(self, mismatch: Mismatch) -> None:
        self.mismatches.append(mismatch)

    def list_mismatches(self, run_id: ReconciliationRunId) -> tuple[Mismatch, ...]:
        return tuple(item for item in self.mismatches if item.run_id == run_id)

    def add_resolution(self, resolution: Resolution) -> None:
        self.resolutions.append(resolution)

    def save_resolution(self, resolution: Resolution) -> None:
        return None

    def list_resolutions(self, run_id: ReconciliationRunId) -> tuple[Resolution, ...]:
        return tuple(item for item in self.resolutions if item.run_id == run_id)

    def checkpoint(self) -> None:
        return None


class InternalPort:
    def __init__(self, snapshot: InternalSnapshot) -> None:
        self._snapshot = snapshot

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> InternalSnapshot:
        _ = account_id, scope
        return self._snapshot


class BrokerPort:
    def __init__(self, snapshot: BrokerSnapshot) -> None:
        self._snapshot = snapshot

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> BrokerSnapshot:
        _ = account_id, scope
        return self._snapshot


def main() -> None:
    now = datetime(2026, 10, 22, 20, tzinfo=UTC)
    account_id = AccountId.new()
    internal = InternalSnapshot(
        account_id=account_id,
        orders=(),
        fills=(),
        positions=(),
        balances=(),
        captured_at=now,
        watermark=SnapshotWatermark(captured_at=now, internal_version=1),
        completeness=SnapshotCompleteness.COMPLETE,
    )
    broker = BrokerSnapshot(
        account_id=account_id,
        provider="example",
        orders=(),
        fills=(),
        positions=(),
        balances=(),
        captured_at=now,
        watermark=SnapshotWatermark(captured_at=now, provider_as_of=now),
        completeness=SnapshotCompleteness.COMPLETE,
    )
    service = ReconcileAccount(
        repository=cast(ReconciliationRepository, MemoryRepository()),
        internal_snapshots=InternalPort(internal),
        broker_snapshots=BrokerPort(broker),
        clock=FakeClock.at(now),
    )
    outcome = service.execute(
        account_id=account_id,
        trigger=ReconciliationTrigger.MANUAL,
        correlation_id=CorrelationId.new(),
    )

    status = outcome.run.result_status
    confidence = outcome.run.confidence
    if status is None or confidence is None:
        raise RuntimeError("Manual reconciliation did not produce a final result.")

    print(f"status: {status.value}")
    print(f"confidence: {confidence.value}")
    print(f"mismatches: {len(outcome.mismatches)}")


if __name__ == "__main__":
    main()
