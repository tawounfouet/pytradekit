"""LOT-08 end-to-end reconciliation and recovery qualification."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.execution import (
    CancelResult,
    CancelStatus,
    ExecutionReport,
    ExecutionStatus,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.orders import (
    ExecutionCertainty,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import (
    HandleExecutionReport,
    SubmitOrder,
    SubmitOrderCommand,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation import (
    BrokerSnapshot,
    CanonicalOrder,
    CanonicalPosition,
    ConsistencyStatus,
    InternalSnapshot,
    Mismatch,
    MismatchSeverity,
    MismatchType,
    ReconciliationRun,
    ReconciliationRunId,
    ReconciliationRunStatus,
    ReconciliationScope,
    ReconciliationTrigger,
    RecoveryState,
    Resolution,
    ResolutionStatus,
    ResolutionType,
    SnapshotCompleteness,
    SnapshotWatermark,
    StateConfidence,
)
from pytradekit.reconciliation.application import (
    ConsistencyAdmissionPolicy,
    ConsistencyRegistry,
    ReconcileAccount,
    RecoveryWorkflowCoordinator,
    UnsafeConsistencyError,
)
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Quantity,
)
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 18, tzinfo=UTC)
USD = Currency("USD")

_ACTIVE = {
    ReconciliationRunStatus.CREATED,
    ReconciliationRunStatus.CAPTURING,
    ReconciliationRunStatus.COMPARING,
    ReconciliationRunStatus.RESOLVING,
    ReconciliationRunStatus.VERIFYING,
}


class MemoryRepository:
    """In-memory evidence repository with active-run semantics."""

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
        return tuple(run for run in self.runs.values() if run.status in _ACTIVE)

    def list_stale(self, *, stale_before: datetime) -> tuple[ReconciliationRun, ...]:
        return tuple(
            run
            for run in self.list_active()
            if run.started_at < stale_before
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
    """Stable internal snapshot with one-shot outage injection."""

    def __init__(self, snapshot: InternalSnapshot) -> None:
        self.snapshot = snapshot
        self.fail_next = False
        self.capture_count = 0

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> InternalSnapshot:
        self.capture_count += 1
        if self.fail_next:
            self.fail_next = False
            raise ConnectionError("synthetic durable-state outage")
        assert account_id == self.snapshot.account_id
        _ = scope
        return self.snapshot


class BrokerPort:
    """Stable broker snapshot with one-shot disconnect injection."""

    def __init__(self, snapshot: BrokerSnapshot) -> None:
        self.snapshot = snapshot
        self.fail_next = False
        self.capture_count = 0

    def capture(
        self,
        *,
        account_id: AccountId,
        scope: ReconciliationScope,
    ) -> BrokerSnapshot:
        self.capture_count += 1
        if self.fail_next:
            self.fail_next = False
            raise ConnectionError("synthetic broker disconnect")
        assert account_id == self.snapshot.account_id
        _ = scope
        return self.snapshot


class UncertainThenAcceptedExecution:
    """One economic submit attempt followed by read-side proof of acceptance."""

    def __init__(self) -> None:
        self.submit_calls = 0
        self.query_calls = 0

    def submit(self, order: Order) -> SubmissionResult:
        self.submit_calls += 1
        return SubmissionResult(
            status=SubmissionStatus.UNCERTAIN,
            reason="synthetic post-accept response loss",
        )

    def cancel(self, order: Order) -> CancelResult:
        _ = order
        return CancelResult(
            status=CancelStatus.REJECTED,
            reason="not used by qualification",
        )

    def query_order(self, order: Order) -> ExecutionReport | None:
        self.query_calls += 1
        return ExecutionReport(
            order_id=order.id,
            status=ExecutionStatus.ACCEPTED,
            occurred_at=NOW,
            correlation_id=order.correlation_id,
            external_order_id="provider-order-accepted",
        )


def _internal(
    account_id: AccountId,
    *,
    completeness: SnapshotCompleteness = SnapshotCompleteness.COMPLETE,
    positions: tuple[CanonicalPosition, ...] = (),
) -> InternalSnapshot:
    return InternalSnapshot(
        account_id=account_id,
        orders=(),
        fills=(),
        positions=positions,
        balances=(),
        captured_at=NOW,
        watermark=SnapshotWatermark(
            captured_at=NOW,
            internal_version=1,
        ),
        completeness=completeness,
    )


def _broker(
    account_id: AccountId,
    *,
    completeness: SnapshotCompleteness = SnapshotCompleteness.COMPLETE,
    orders: tuple[CanonicalOrder, ...] = (),
    positions: tuple[CanonicalPosition, ...] = (),
) -> BrokerSnapshot:
    return BrokerSnapshot(
        account_id=account_id,
        provider="qualification",
        orders=orders,
        fills=(),
        positions=positions,
        balances=(),
        captured_at=NOW,
        watermark=SnapshotWatermark(
            captured_at=NOW,
            provider_as_of=NOW,
        ),
        completeness=completeness,
    )


def _workflow(
    *,
    internal: InternalPort,
    broker: BrokerPort,
) -> tuple[
    RecoveryWorkflowCoordinator,
    ConsistencyRegistry,
    ConsistencyAdmissionPolicy,
]:
    registry = ConsistencyRegistry()
    service = ReconcileAccount(
        repository=MemoryRepository(),
        internal_snapshots=internal,
        broker_snapshots=broker,
        clock=FakeClock.at(NOW),
        evidence_sink=registry,
    )
    workflows = RecoveryWorkflowCoordinator(
        reconciliation=service,
        containment=registry.clear,
    )
    return workflows, registry, ConsistencyAdmissionPolicy(registry)


def test_clean_startup_proves_consistent_high_and_allows_new_risk() -> None:
    account_id = AccountId.new()
    workflows, registry, policy = _workflow(
        internal=InternalPort(_internal(account_id)),
        broker=BrokerPort(_broker(account_id)),
    )

    outcome = workflows.startup(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    assert outcome.run.trigger is ReconciliationTrigger.STARTUP
    assert outcome.run.result_status is ConsistencyStatus.CONSISTENT
    assert outcome.run.confidence is StateConfidence.HIGH
    assert workflows.state is RecoveryState.RECOVERED
    assert registry.get(account_id) is not None
    policy.ensure_risk_increase_allowed(account_id)


def test_broker_disconnect_invalidates_old_readiness_until_reconnect_converges() -> None:
    account_id = AccountId.new()
    internal = InternalPort(_internal(account_id))
    broker = BrokerPort(_broker(account_id))
    workflows, registry, policy = _workflow(internal=internal, broker=broker)

    workflows.startup(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )
    policy.ensure_risk_increase_allowed(account_id)

    broker.fail_next = True
    with pytest.raises(ConnectionError, match="broker disconnect"):
        workflows.reconnect(
            account_id=account_id,
            correlation_id=CorrelationId.new(),
        )

    assert workflows.state is RecoveryState.FAILED
    assert registry.get(account_id) is None
    with pytest.raises(UnsafeConsistencyError):
        policy.ensure_risk_increase_allowed(account_id)

    recovered = workflows.reconnect(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    assert recovered.run.trigger is ReconciliationTrigger.RECONNECT
    assert recovered.run.result_status is ConsistencyStatus.CONSISTENT
    assert recovered.run.confidence is StateConfidence.HIGH
    assert workflows.state is RecoveryState.RECOVERED
    policy.ensure_risk_increase_allowed(account_id)


def test_durable_state_outage_fails_before_broker_read_and_recovers_fresh() -> None:
    account_id = AccountId.new()
    internal = InternalPort(_internal(account_id))
    broker = BrokerPort(_broker(account_id))
    workflows, registry, policy = _workflow(internal=internal, broker=broker)

    workflows.startup(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )
    policy.ensure_risk_increase_allowed(account_id)

    before = broker.capture_count
    internal.fail_next = True
    with pytest.raises(ConnectionError, match="durable-state outage"):
        workflows.incident(
            account_id=account_id,
            correlation_id=CorrelationId.new(),
        )

    assert broker.capture_count == before
    assert registry.get(account_id) is None
    assert workflows.state is RecoveryState.FAILED
    with pytest.raises(UnsafeConsistencyError):
        policy.ensure_risk_increase_allowed(account_id)

    recovered = workflows.incident(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    assert recovered.run.result_status is ConsistencyStatus.CONSISTENT
    assert recovered.run.confidence is StateConfidence.HIGH
    policy.ensure_risk_increase_allowed(account_id)


def test_partial_snapshot_cannot_restore_high_confidence_or_risk_admission() -> None:
    account_id = AccountId.new()
    workflows, _, policy = _workflow(
        internal=InternalPort(_internal(account_id)),
        broker=BrokerPort(
            _broker(
                account_id,
                completeness=SnapshotCompleteness.PARTIAL,
            )
        ),
    )

    outcome = workflows.periodic(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    assert outcome.run.confidence is not StateConfidence.HIGH
    assert outcome.run.result_status is not ConsistencyStatus.CONSISTENT
    assert workflows.state is RecoveryState.BLOCKED
    assert any(
        item.type is MismatchType.SNAPSHOT_INCOMPLETE
        for item in outcome.mismatches
    )
    with pytest.raises(UnsafeConsistencyError):
        policy.ensure_risk_increase_allowed(account_id)


def test_unknown_external_manual_order_remains_blocked_for_review() -> None:
    account_id = AccountId.new()
    manual = CanonicalOrder(
        order_id=None,
        client_order_id="manual-client",
        external_order_id="broker-manual-order",
        status="accepted",
        filled_quantity=Decimal("0"),
    )
    workflows, _, policy = _workflow(
        internal=InternalPort(_internal(account_id)),
        broker=BrokerPort(_broker(account_id, orders=(manual,))),
    )

    outcome = workflows.incident(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    assert outcome.run.result_status is ConsistencyStatus.INCONSISTENT
    assert outcome.run.confidence is StateConfidence.LOW
    assert workflows.state is RecoveryState.BLOCKED
    mismatch = next(
        item
        for item in outcome.mismatches
        if item.type is MismatchType.UNKNOWN_EXTERNAL_ORDER
    )
    assert mismatch.severity is MismatchSeverity.CRITICAL
    resolution = next(
        item for item in outcome.resolutions if item.mismatch_id == mismatch.id
    )
    assert resolution.type is ResolutionType.MANUAL_REVIEW
    assert resolution.status is ResolutionStatus.PLANNED
    with pytest.raises(UnsafeConsistencyError):
        policy.ensure_risk_increase_allowed(account_id)


def test_critical_position_divergence_blocks_runtime_until_causality_is_known() -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    local = CanonicalPosition(
        instrument_id=instrument_id,
        quantity=Decimal("1"),
        average_price=Decimal("100"),
        currency=USD,
    )
    remote = CanonicalPosition(
        instrument_id=instrument_id,
        quantity=Decimal("2"),
        average_price=Decimal("100"),
        currency=USD,
    )
    workflows, _, policy = _workflow(
        internal=InternalPort(_internal(account_id, positions=(local,))),
        broker=BrokerPort(_broker(account_id, positions=(remote,))),
    )

    outcome = workflows.incident(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    mismatch = next(
        item
        for item in outcome.mismatches
        if item.type is MismatchType.POSITION_QUANTITY_MISMATCH
    )
    assert mismatch.severity is MismatchSeverity.CRITICAL
    assert outcome.run.result_status is ConsistencyStatus.INCONSISTENT
    assert outcome.run.confidence is StateConfidence.LOW
    assert workflows.state is RecoveryState.BLOCKED
    with pytest.raises(UnsafeConsistencyError):
        policy.ensure_risk_increase_allowed(account_id)


def test_submit_uncertainty_converges_by_query_without_second_submit() -> None:
    clock = FakeClock.at(NOW)
    orders = InMemoryOrderRepository()
    execution = UncertainThenAcceptedExecution()
    submit = SubmitOrder(
        repository=orders,
        execution=execution,
        clock=clock,
    )
    handle = HandleExecutionReport(repository=orders)

    result = submit.execute(
        SubmitOrderCommand(
            instrument_id=InstrumentId.new(),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity(Decimal("1")),
            time_in_force=TimeInForce.DAY,
            correlation_id=CorrelationId.new(),
        )
    )

    assert result.submission_status is SubmissionStatus.UNCERTAIN
    uncertain = orders.get(result.order.order_id)
    assert uncertain is not None
    assert uncertain.status is OrderStatus.SUBMITTED
    assert uncertain.execution_certainty is ExecutionCertainty.UNCERTAIN

    report = execution.query_order(uncertain)
    assert report is not None
    reconciled = handle.execute(report)

    assert reconciled.status is OrderStatus.ACCEPTED
    assert reconciled.execution_certainty is ExecutionCertainty.KNOWN
    assert execution.submit_calls == 1
    assert execution.query_calls == 1

    account_id = AccountId.new()
    workflows, _, policy = _workflow(
        internal=InternalPort(_internal(account_id)),
        broker=BrokerPort(_broker(account_id)),
    )
    outcome = workflows.submit_uncertainty(
        account_id=account_id,
        correlation_id=CorrelationId.new(),
    )

    assert outcome.run.trigger is ReconciliationTrigger.SUBMIT_UNCERTAINTY
    assert outcome.run.result_status is ConsistencyStatus.CONSISTENT
    assert outcome.run.confidence is StateConfidence.HIGH
    assert execution.submit_calls == 1
    policy.ensure_risk_increase_allowed(account_id)
