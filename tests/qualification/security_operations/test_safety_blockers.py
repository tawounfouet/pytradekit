"""Release-blocker qualification for KillSwitch and RiskOverride semantics."""

from datetime import UTC, datetime, timedelta
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
from pytradekit.orders.ports import OrderSafetyDeniedError, RiskGateResult
from pytradekit.portfolio.domain import AccountId
from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    RecoveryState,
    StateConfidence,
)
from pytradekit.runtime.operations import RuntimeLifecycleState
from pytradekit.safety import (
    KillSwitch,
    KillSwitchId,
    KillSwitchScope,
    KillSwitchState,
    RiskOverride,
    RiskOverrideId,
    RiskOverrideScope,
    SafetyEvidence,
    SafetyGate,
)
from pytradekit.safety.adapters import (
    InMemoryKillSwitchRepository,
    InMemoryRiskOverrideRepository,
    InMemorySafetyEvidenceProvider,
    OrdersSafetyGate,
)
from pytradekit.security import ActorId
from pytradekit.shared import (
    CorrelationId,
    Currency,
    InstrumentId,
    Money,
    Price,
    Quantity,
)
from pytradekit.testing import ExplicitTestOrderAuthorizationGate, FakeClock

NOW = datetime(2026, 10, 22, 22, 10, tzinfo=UTC)


class _CountingExecutionPort:
    def __init__(self) -> None:
        self.submit_calls = 0

    def submit(self, order: Order) -> SubmissionResult:
        self.submit_calls += 1
        return SubmissionResult(
            status=SubmissionStatus.ACKNOWLEDGED,
            external_order_id=f"external-{order.id}",
        )

    def cancel(self, order: Order) -> CancelResult:
        _ = order
        return CancelResult(status=CancelStatus.ACKNOWLEDGED)

    def query_order(self, order: Order) -> ExecutionReport | None:
        _ = order
        return None


class _RejectingRiskPort:
    def evaluate(
        self,
        order: Order,
        *,
        account_id: AccountId,
        reference_price: Price | None,
        strategy_id: str | None,
        start_of_day_nav: Money | None,
    ) -> RiskGateResult:
        del order, account_id, reference_price, strategy_id, start_of_day_nav
        return RiskGateResult(
            allowed=False,
            decision="reject",
            violation_codes=("MAX_ORDER_SIZE_EXCEEDED",),
            risk_increasing=True,
        )


def _evidence(consistency: ConsistencyStatus) -> SafetyEvidence:
    return SafetyEvidence(
        consistency_status=consistency,
        state_confidence=StateConfidence.HIGH,
        recovery_state=RecoveryState.IDLE,
        runtime_lifecycle=RuntimeLifecycleState.READY,
        trading_ready=True,
    )


def _active_override(
    *,
    account_id: AccountId,
    instrument_id: InstrumentId,
    valid_until: datetime,
) -> RiskOverride:
    actor_id = ActorId.new()
    pending = RiskOverride(
        id=RiskOverrideId.new(),
        scope=RiskOverrideScope(
            account_id=str(account_id),
            risk_rule="MAX_ORDER_SIZE_EXCEEDED",
            instrument_id=str(instrument_id),
        ),
        reason="qualified temporary exception",
        requested_by=actor_id,
        created_at=NOW - timedelta(minutes=10),
        valid_from=NOW - timedelta(minutes=5),
        valid_until=valid_until,
        correlation_id=CorrelationId.new(),
    )
    return pending.approve(
        actor_id=actor_id,
        occurred_at=NOW - timedelta(minutes=4),
    )


def _command(
    *,
    account_id: AccountId,
    instrument_id: InstrumentId,
) -> SubmitOrderCommand:
    return SubmitOrderCommand(
        account_id=account_id,
        order_id=OrderId.new(),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity(Decimal("1")),
        time_in_force=TimeInForce.DAY,
        correlation_id=CorrelationId.new(),
        reference_price=Price(Decimal("100"), Currency("USD")),
    )


def _submit(
    *,
    account_id: AccountId,
    instrument_id: InstrumentId,
    consistency: ConsistencyStatus,
    override: RiskOverride,
    kill_switch: KillSwitch | None = None,
) -> tuple[SubmitOrder, _CountingExecutionPort]:
    evidence = InMemorySafetyEvidenceProvider()
    evidence.set(account_id, _evidence(consistency))

    overrides = InMemoryRiskOverrideRepository()
    overrides.save(override, expected_version=None)

    switches = InMemoryKillSwitchRepository()
    if kill_switch is not None:
        switches.save(kill_switch, expected_version=None)

    execution = _CountingExecutionPort()
    submit = SubmitOrder(
        repository=InMemoryOrderRepository(),
        execution=execution,
        clock=FakeClock.at(NOW),
        risk=_RejectingRiskPort(),
        authorization_gate=ExplicitTestOrderAuthorizationGate(),
        safety_gate=OrdersSafetyGate(
            gate=SafetyGate(clock=FakeClock.at(NOW)),
            evidence=evidence,
            kill_switches=switches,
            risk_overrides=overrides,
        ),
    )
    return submit, execution


def test_kill_switch_dominates_matching_override() -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    override = _active_override(
        account_id=account_id,
        instrument_id=instrument_id,
        valid_until=NOW + timedelta(minutes=5),
    )
    switch = KillSwitch(
        id=KillSwitchId.new(),
        state=KillSwitchState.ACTIVE,
        scope=KillSwitchScope.ACCOUNT,
        environment="PAPER",
        scope_id=str(account_id),
        reason="qualification containment",
        activated_by=ActorId.new(),
        activated_at=NOW,
    )
    submit, execution = _submit(
        account_id=account_id,
        instrument_id=instrument_id,
        consistency=ConsistencyStatus.CONSISTENT,
        override=override,
        kill_switch=switch,
    )

    with pytest.raises(OrderSafetyDeniedError):
        submit.execute(
            _command(account_id=account_id, instrument_id=instrument_id)
        )

    assert execution.submit_calls == 0


@pytest.mark.parametrize(
    "consistency",
    [ConsistencyStatus.UNKNOWN, ConsistencyStatus.INCONSISTENT],
)
def test_override_cannot_manufacture_trusted_economic_truth(
    consistency: ConsistencyStatus,
) -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    override = _active_override(
        account_id=account_id,
        instrument_id=instrument_id,
        valid_until=NOW + timedelta(minutes=5),
    )
    submit, execution = _submit(
        account_id=account_id,
        instrument_id=instrument_id,
        consistency=consistency,
        override=override,
    )

    with pytest.raises(OrderSafetyDeniedError):
        submit.execute(
            _command(account_id=account_id, instrument_id=instrument_id)
        )

    assert execution.submit_calls == 0


def test_expired_override_cannot_bypass_risk_policy() -> None:
    account_id = AccountId.new()
    instrument_id = InstrumentId.new()
    override = _active_override(
        account_id=account_id,
        instrument_id=instrument_id,
        valid_until=NOW,
    )
    submit, execution = _submit(
        account_id=account_id,
        instrument_id=instrument_id,
        consistency=ConsistencyStatus.CONSISTENT,
        override=override,
    )

    result = submit.execute(
        _command(account_id=account_id, instrument_id=instrument_id)
    )

    assert result.submission_status is None
    assert result.risk_decision == "reject"
    assert result.risk_override_applied is False
    assert "RISK_POLICY_DENIED" in result.safety_reason_codes
    assert execution.submit_calls == 0
    assert override.is_active(NOW - timedelta(seconds=1))
    assert not override.is_active(NOW)
