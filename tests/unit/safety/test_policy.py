"""Unit qualification for SafetyState and SafetyDecision."""

from datetime import UTC, datetime

from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    RecoveryState,
    StateConfidence,
)
from pytradekit.runtime.operations import RuntimeLifecycleState
from pytradekit.safety import (
    SafetyAction,
    SafetyEvidence,
    SafetyGate,
    SafetyReason,
    SafetyState,
)
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)


def _evidence(
    *,
    consistency: ConsistencyStatus = ConsistencyStatus.CONSISTENT,
    confidence: StateConfidence = StateConfidence.HIGH,
    recovery: RecoveryState = RecoveryState.IDLE,
    lifecycle: RuntimeLifecycleState = RuntimeLifecycleState.READY,
    trading_ready: bool = True,
) -> SafetyEvidence:
    return SafetyEvidence(
        consistency_status=consistency,
        state_confidence=confidence,
        recovery_state=recovery,
        runtime_lifecycle=lifecycle,
        trading_ready=trading_ready,
    )


def test_safe_evidence_allows_risk_increase() -> None:
    gate = SafetyGate(clock=FakeClock.at(NOW))

    decision = gate.evaluate(
        action=SafetyAction.SUBMIT_RISK_INCREASING,
        evidence=_evidence(),
        risk_allowed=True,
    )

    assert decision.allowed
    assert decision.state is SafetyState.SAFE
    assert decision.reason_codes == (SafetyReason.ALLOWED,)


def test_unknown_truth_denies_risk_increase_even_when_authorized() -> None:
    gate = SafetyGate(clock=FakeClock.at(NOW))

    decision = gate.evaluate(
        action=SafetyAction.SUBMIT_RISK_INCREASING,
        evidence=_evidence(consistency=ConsistencyStatus.UNKNOWN),
        risk_allowed=True,
        authorization_allowed=True,
    )

    assert not decision.allowed
    assert decision.state is SafetyState.UNKNOWN
    assert SafetyReason.ECONOMIC_TRUTH_UNKNOWN in decision.reason_codes


def test_inconsistent_truth_denies_risk_increase_even_when_authorized() -> None:
    gate = SafetyGate(clock=FakeClock.at(NOW))

    decision = gate.evaluate(
        action=SafetyAction.SUBMIT_RISK_INCREASING,
        evidence=_evidence(consistency=ConsistencyStatus.INCONSISTENT),
        risk_allowed=True,
        authorization_allowed=True,
    )

    assert not decision.allowed
    assert decision.state is SafetyState.RESTRICTED
    assert SafetyReason.ECONOMIC_TRUTH_INCONSISTENT in decision.reason_codes


def test_cancel_remains_available_in_restricted_state() -> None:
    gate = SafetyGate(clock=FakeClock.at(NOW))

    decision = gate.evaluate(
        action=SafetyAction.CANCEL_ORDER,
        evidence=_evidence(consistency=ConsistencyStatus.INCONSISTENT),
    )

    assert decision.allowed
    assert decision.reason_codes == (SafetyReason.CANCEL_ALLOWED,)


def test_reconciliation_remains_available_with_unknown_truth() -> None:
    gate = SafetyGate(clock=FakeClock.at(NOW))

    decision = gate.evaluate(
        action=SafetyAction.RUN_RECONCILIATION,
        evidence=_evidence(consistency=ConsistencyStatus.UNKNOWN),
    )

    assert decision.allowed
    assert decision.reason_codes == (SafetyReason.RECONCILIATION_ALLOWED,)


def test_admin_like_authorization_cannot_bypass_unknown_safety() -> None:
    gate = SafetyGate(clock=FakeClock.at(NOW))

    decision = gate.evaluate(
        action=SafetyAction.SUBMIT_RISK_INCREASING,
        evidence=_evidence(confidence=StateConfidence.UNKNOWN),
        risk_allowed=True,
        authorization_allowed=True,
    )

    assert not decision.allowed
    assert decision.state is SafetyState.UNKNOWN
