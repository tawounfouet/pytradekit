"""End-to-end LOT-05 health and readiness qualification."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pytradekit.execution import (
    CancelResult,
    CancelStatus,
    ExecutionReport,
    SubmissionResult,
    SubmissionStatus,
)
from pytradekit.operations import (
    HealthComponent,
    HealthRegistry,
    HealthReport,
    HealthStatus,
    OperationalReadinessService,
)
from pytradekit.operations.adapters import HealthAwareSafetyEvidenceProvider
from pytradekit.operations.application import ApplyOperationalReadiness
from pytradekit.orders.domain import (
    Order,
    OrderId,
    OrderSide,
    TimeInForce,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    RecoveryState,
    StateConfidence,
)
from pytradekit.runtime import (
    ReadinessCheck,
    ReadinessCheckStatus,
    TradingReadinessReport,
)
from pytradekit.runtime.operations import (
    AdmissionControlledExecutionPort,
    RuntimeAdmissionClosedError,
    RuntimeAdmissionGate,
    RuntimeLifecycleState,
)
from pytradekit.safety import SafetyAction, SafetyEvidence, SafetyGate
from pytradekit.safety.adapters import InMemorySafetyEvidenceProvider
from pytradekit.shared import CorrelationId, InstrumentId, Quantity
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 21, 0, tzinfo=UTC)


class CountingExecution:
    def __init__(self) -> None:
        self.submit_calls = 0

    def submit(self, order: Order) -> SubmissionResult:
        self.submit_calls += 1
        return SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id=f"external-{order.id}",
        )

    def cancel(self, order: Order) -> CancelResult:
        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> ExecutionReport | None:
        return None


def _order() -> Order:
    order = Order.create_market(
        order_id=OrderId.new(),
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
    )
    order.validate(occurred_at=NOW)
    order.mark_submitted(occurred_at=NOW)
    return order


def _trading_ready() -> TradingReadinessReport:
    return TradingReadinessReport(
        provider="alpaca",
        environment="PAPER",
        account="********1234",
        checks=(ReadinessCheck("qualified", ReadinessCheckStatus.PASS, "ok"),),
        consistency_status=ConsistencyStatus.CONSISTENT,
        state_confidence=StateConfidence.HIGH,
    )


def _registry(*, database: HealthStatus) -> HealthRegistry:
    registry = HealthRegistry()
    for component, status in (
        (HealthComponent.DATABASE, database),
        (HealthComponent.BROKER_COMMAND, HealthStatus.HEALTHY),
        (HealthComponent.RUNTIME, HealthStatus.HEALTHY),
    ):
        registry.update(
            HealthReport(
                component=component,
                status=status,
                observed_at=NOW,
                message=status.value.lower(),
                last_success_at=(
                    NOW if status is HealthStatus.HEALTHY else None
                ),
            )
        )
    return registry


def test_database_failure_closes_runtime_admission_before_provider() -> None:
    health = _registry(database=HealthStatus.UNHEALTHY)
    readiness = OperationalReadinessService().evaluate(
        lifecycle=RuntimeLifecycleState.READY,
        health=health,
        trading=_trading_ready(),
        observed_at=NOW,
    )
    gate = RuntimeAdmissionGate()
    gate.mark_ready()
    ApplyOperationalReadiness(gate).execute(readiness)
    execution = CountingExecution()
    controlled = AdmissionControlledExecutionPort(
        delegate=execution,
        gate=gate,
    )

    with pytest.raises(RuntimeAdmissionClosedError):
        controlled.submit(_order())

    assert execution.submit_calls == 0
    assert gate.state is RuntimeLifecycleState.DEGRADED


def test_database_failure_projects_into_safety_without_changing_economic_truth() -> None:
    account_id = AccountId.new()
    base = InMemorySafetyEvidenceProvider()
    base.set(
        account_id,
        SafetyEvidence(
            consistency_status=ConsistencyStatus.CONSISTENT,
            state_confidence=StateConfidence.HIGH,
            recovery_state=RecoveryState.IDLE,
            runtime_lifecycle=RuntimeLifecycleState.READY,
            trading_ready=True,
        ),
    )
    health_aware = HealthAwareSafetyEvidenceProvider(
        delegate=base,
        health=_registry(database=HealthStatus.UNHEALTHY),
        clock=FakeClock.at(NOW),
    )
    evidence = health_aware.get(account_id)
    assert evidence is not None
    decision = SafetyGate(clock=FakeClock.at(NOW)).evaluate(
        action=SafetyAction.SUBMIT_RISK_INCREASING,
        evidence=evidence,
        risk_allowed=True,
    )

    assert not decision.allowed
    assert decision.state.value == "RESTRICTED"
    assert "CRITICAL_HEALTH_UNHEALTHY" in {
        reason.value for reason in decision.reason_codes
    }
