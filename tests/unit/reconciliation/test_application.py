"""LOT-04 generic reconciliation application pipeline."""

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
        return ()

    def list_stale(self, *, stale_before: datetime) -> tuple[ReconciliationRun, ...]:
        return ()

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


class StaticSnapshots:
    def __init__(
        self,
        internal: InternalSnapshot,
        broker: BrokerSnapshot,
    ) -> None:
        self.internal = internal
        self.broker = broker

    def capture_internal(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> InternalSnapshot:
        return self.internal

    def capture_broker(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> BrokerSnapshot:
        return self.broker


class InternalPort:
    def __init__(self, snapshots: StaticSnapshots) -> None:
        self._snapshots = snapshots

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> InternalSnapshot:
        return self._snapshots.capture_internal(account_id=account_id, scope=scope)


class BrokerPort:
    def __init__(self, snapshots: StaticSnapshots) -> None:
        self._snapshots = snapshots

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> BrokerSnapshot:
        return self._snapshots.capture_broker(account_id=account_id, scope=scope)


def test_clean_account_completes_consistent_high() -> None:
    now = datetime(2026, 10, 22, 12, tzinfo=UTC)
    account_id = AccountId.new()
    watermark = SnapshotWatermark(captured_at=now)
    internal = InternalSnapshot(
        account_id=account_id,
        orders=(),
        fills=(),
        positions=(),
        balances=(),
        captured_at=now,
        watermark=watermark,
        completeness=SnapshotCompleteness.COMPLETE,
    )
    broker = BrokerSnapshot(
        account_id=account_id,
        provider="test",
        orders=(),
        fills=(),
        positions=(),
        balances=(),
        captured_at=now,
        watermark=watermark,
        completeness=SnapshotCompleteness.COMPLETE,
    )
    snapshots = StaticSnapshots(internal, broker)
    repository = MemoryRepository()
    service = ReconcileAccount(
        repository=cast(ReconciliationRepository, repository),
        internal_snapshots=InternalPort(snapshots),
        broker_snapshots=BrokerPort(snapshots),
        clock=FakeClock(now),
    )

    outcome = service.execute(
        account_id=account_id,
        trigger=ReconciliationTrigger.STARTUP,
        correlation_id=CorrelationId.new(),
    )

    assert outcome.run.result_status is not None
    assert outcome.run.result_status.value == "CONSISTENT"
    assert outcome.run.confidence is not None
    assert outcome.run.confidence.value == "HIGH"
    assert outcome.mismatches == ()
