"""End-to-end LOT-03 safety qualification before provider side effects."""

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
from pytradekit.orders.adapters import InMemoryOrderRepository
from pytradekit.orders.application import SubmitOrder, SubmitOrderCommand
from pytradekit.orders.domain import Order, OrderId, OrderSide, OrderType, TimeInForce
from pytradekit.orders.ports import OrderSafetyDeniedError
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    RecoveryState,
    StateConfidence,
)
from pytradekit.runtime.operations import RuntimeLifecycleState
from pytradekit.safety import SafetyEvidence, SafetyGate
from pytradekit.safety.adapters import (
    InMemorySafetyEvidenceProvider,
    OrdersSafetyGate,
)
from pytradekit.shared import CorrelationId, InstrumentId, Quantity
from pytradekit.testing import ExplicitTestOrderAuthorizationGate, FakeClock

NOW = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)


class CountingExecutionPort:
    """Execution spy proving safety denial stops before the provider."""

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


def _command(account_id: AccountId, order_id: OrderId) -> SubmitOrderCommand:
    return SubmitOrderCommand(
        account_id=account_id,
        order_id=order_id,
        instrument_id=InstrumentId.new(),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
    )


def test_authorized_submit_is_still_blocked_by_unknown_safety() -> None:
    account_id = AccountId.new()
    order_id = OrderId.new()
    evidence = InMemorySafetyEvidenceProvider()
    evidence.set(
        account_id,
        SafetyEvidence(
            consistency_status=ConsistencyStatus.UNKNOWN,
            state_confidence=StateConfidence.UNKNOWN,
            recovery_state=RecoveryState.IDLE,
            runtime_lifecycle=RuntimeLifecycleState.READY,
            trading_ready=True,
        ),
    )
    execution = CountingExecutionPort()
    repository = InMemoryOrderRepository()
    safety = OrdersSafetyGate(
        gate=SafetyGate(clock=FakeClock.at(NOW)),
        evidence=evidence,
    )
    submit = SubmitOrder(
        repository=repository,
        execution=execution,
        clock=FakeClock.at(NOW),
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
        safety_gate=safety,
    )

    with pytest.raises(OrderSafetyDeniedError):
        submit.execute(_command(account_id, order_id))

    assert execution.submit_calls == 0
    assert repository.get(order_id) is None


def test_safe_evidence_allows_authorized_submit() -> None:
    account_id = AccountId.new()
    evidence = InMemorySafetyEvidenceProvider()
    evidence.set(
        account_id,
        SafetyEvidence(
            consistency_status=ConsistencyStatus.CONSISTENT,
            state_confidence=StateConfidence.HIGH,
            recovery_state=RecoveryState.IDLE,
            runtime_lifecycle=RuntimeLifecycleState.READY,
            trading_ready=True,
        ),
    )
    execution = CountingExecutionPort()
    safety = OrdersSafetyGate(
        gate=SafetyGate(clock=FakeClock.at(NOW)),
        evidence=evidence,
    )
    submit = SubmitOrder(
        repository=InMemoryOrderRepository(),
        execution=execution,
        clock=FakeClock.at(NOW),
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
        safety_gate=safety,
    )

    result = submit.execute(_command(account_id, OrderId.new()))

    assert result.submission_status is SubmissionStatus.ACKNOWLEDGED
    assert execution.submit_calls == 1
    assert result.safety_reason_codes == ("ALLOWED",)
