"""LOT-08 stale reconciliation qualification."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest

from pytradekit.orders import OrderId
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation import (
    BrokerSnapshot,
    CanonicalFill,
    ConsistencyStatus,
    ExternalActivityOrigin,
    InternalSnapshot,
    Mismatch,
    MismatchType,
    ReconciliationRun,
    ReconciliationRunId,
    ReconciliationScope,
    ReconciliationTrigger,
    Resolution,
    ResolutionType,
    SnapshotCompleteness,
    SnapshotWatermark,
    StateConfidence,
)
from pytradekit.reconciliation.application import (
    ReconcileAccount,
    StaleReconciliationError,
)
from pytradekit.reconciliation.ports import (
    ReconciliationRepository,
    ResolutionExecutorPort,
)
from pytradekit.shared import CorrelationId, Currency
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 19, tzinfo=UTC)
USD = Currency("USD")


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


class SequenceInternal:
    def __init__(self, snapshots: tuple[InternalSnapshot, ...]) -> None:
        self._snapshots = snapshots
        self.calls = 0

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> InternalSnapshot:
        _ = account_id, scope
        index = min(self.calls, len(self._snapshots) - 1)
        self.calls += 1
        return self._snapshots[index]


class StaticBroker:
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


class RecordingExecutor:
    def __init__(self) -> None:
        self.apply_calls = 0

    def supports(self, resolution_type: ResolutionType) -> bool:
        return resolution_type is ResolutionType.IMPORT_MISSING_EXTERNAL_EVENT

    def apply(
        self,
        *,
        resolution: Resolution,
        mismatch: Mismatch,
        broker_snapshot: BrokerSnapshot,
    ) -> None:
        _ = resolution, mismatch, broker_snapshot
        self.apply_calls += 1


def _fill(order_id: OrderId) -> CanonicalFill:
    return CanonicalFill(
        external_fill_id="stale-fill-1",
        order_id=order_id,
        external_order_id="stale-provider-order",
        quantity=Decimal("1"),
        price=Decimal("100"),
        currency=USD,
        occurred_at=NOW,
        origin=ExternalActivityOrigin.INTERNAL,
    )


def _internal(
    account_id: AccountId,
    *,
    version: int,
    fills: tuple[CanonicalFill, ...] = (),
) -> InternalSnapshot:
    return InternalSnapshot(
        account_id=account_id,
        orders=(),
        fills=fills,
        positions=(),
        balances=(),
        captured_at=NOW,
        watermark=SnapshotWatermark(
            captured_at=NOW,
            internal_version=version,
        ),
        completeness=SnapshotCompleteness.COMPLETE,
    )


def _broker(account_id: AccountId, fill: CanonicalFill) -> BrokerSnapshot:
    return BrokerSnapshot(
        account_id=account_id,
        provider="qualification",
        orders=(),
        fills=(fill,),
        positions=(),
        balances=(),
        captured_at=NOW,
        watermark=SnapshotWatermark(
            captured_at=NOW,
            provider_as_of=NOW,
        ),
        completeness=SnapshotCompleteness.COMPLETE,
    )


def test_stale_repair_is_rejected_before_side_effect_then_fresh_run_converges() -> None:
    account_id = AccountId.new()
    fill = _fill(OrderId.new())
    repository = MemoryRepository()
    executor = RecordingExecutor()

    stale_service = ReconcileAccount(
        repository=cast(ReconciliationRepository, repository),
        internal_snapshots=SequenceInternal(
            (
                _internal(account_id, version=1),
                _internal(account_id, version=2),
            )
        ),
        broker_snapshots=StaticBroker(_broker(account_id, fill)),
        clock=FakeClock.at(NOW),
        executor=cast(ResolutionExecutorPort, executor),
    )

    with pytest.raises(StaleReconciliationError):
        stale_service.execute(
            account_id=account_id,
            trigger=ReconciliationTrigger.INCIDENT,
            correlation_id=CorrelationId.new(),
            scope=ReconciliationScope.FILLS,
        )

    assert executor.apply_calls == 0
    assert any(
        mismatch.type is MismatchType.STALE_RECONCILIATION
        for mismatch in repository.mismatches
    )
    assert repository.list_active() == ()

    converged = _internal(account_id, version=2, fills=(fill,))
    fresh_service = ReconcileAccount(
        repository=cast(ReconciliationRepository, repository),
        internal_snapshots=SequenceInternal((converged,)),
        broker_snapshots=StaticBroker(_broker(account_id, fill)),
        clock=FakeClock.at(NOW),
    )

    outcome = fresh_service.execute(
        account_id=account_id,
        trigger=ReconciliationTrigger.RECONNECT,
        correlation_id=CorrelationId.new(),
        scope=ReconciliationScope.FILLS,
    )

    assert outcome.run.result_status is ConsistencyStatus.CONSISTENT
    assert outcome.run.confidence is StateConfidence.HIGH
    assert outcome.mismatches == ()
