"""Property qualification for SafetyGate hard invariants."""

from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    RecoveryState,
    StateConfidence,
)
from pytradekit.runtime.operations import RuntimeLifecycleState
from pytradekit.safety import SafetyAction, SafetyEvidence, SafetyGate
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)


@given(
    status=st.sampled_from(
        [ConsistencyStatus.UNKNOWN, ConsistencyStatus.INCONSISTENT]
    ),
    confidence=st.sampled_from(list(StateConfidence)),
)
def test_unknown_or_inconsistent_truth_never_allows_risk_increase(
    status: ConsistencyStatus,
    confidence: StateConfidence,
) -> None:
    gate = SafetyGate(clock=FakeClock.at(NOW))
    evidence = SafetyEvidence(
        consistency_status=status,
        state_confidence=confidence,
        recovery_state=RecoveryState.IDLE,
        runtime_lifecycle=RuntimeLifecycleState.READY,
        trading_ready=True,
    )

    decision = gate.evaluate(
        action=SafetyAction.SUBMIT_RISK_INCREASING,
        evidence=evidence,
        risk_allowed=True,
        authorization_allowed=True,
    )

    assert not decision.allowed
