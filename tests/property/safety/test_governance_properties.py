"""Property qualification for hard safety and governance invariants."""

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    RecoveryState,
    StateConfidence,
)
from pytradekit.runtime.operations import RuntimeLifecycleState
from pytradekit.safety import (
    RiskOverride,
    RiskOverrideId,
    RiskOverrideScope,
    SafetyAction,
    SafetyEvidence,
    SafetyGate,
)
from pytradekit.security import ActorId
from pytradekit.shared import CorrelationId
from pytradekit.testing import FakeClock

NOW = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)


def _safe_evidence(
    *,
    consistency: ConsistencyStatus = ConsistencyStatus.CONSISTENT,
) -> SafetyEvidence:
    return SafetyEvidence(
        consistency_status=consistency,
        state_confidence=StateConfidence.HIGH,
        recovery_state=RecoveryState.IDLE,
        runtime_lifecycle=RuntimeLifecycleState.READY,
        trading_ready=True,
    )


@given(risk_override_active=st.booleans())
def test_kill_switch_always_blocks_risk_increase(
    risk_override_active: bool,
) -> None:
    decision = SafetyGate(clock=FakeClock.at(NOW)).evaluate(
        action=SafetyAction.SUBMIT_RISK_INCREASING,
        evidence=_safe_evidence(),
        risk_allowed=False,
        kill_switch_active=True,
        risk_override_active=risk_override_active,
    )

    assert not decision.allowed
    assert not decision.risk_override_applied


@given(risk_override_active=st.booleans())
def test_unknown_truth_cannot_be_overridden(
    risk_override_active: bool,
) -> None:
    decision = SafetyGate(clock=FakeClock.at(NOW)).evaluate(
        action=SafetyAction.SUBMIT_RISK_INCREASING,
        evidence=_safe_evidence(consistency=ConsistencyStatus.UNKNOWN),
        risk_allowed=False,
        risk_override_active=risk_override_active,
    )

    assert not decision.allowed
    assert not decision.risk_override_applied


@given(seconds=st.integers(min_value=1, max_value=3600))
def test_override_has_no_effect_at_or_after_expiry(seconds: int) -> None:
    actor_id = ActorId.new()
    override = RiskOverride(
        id=RiskOverrideId.new(),
        scope=RiskOverrideScope(account_id="account-1"),
        reason="temporary",
        requested_by=actor_id,
        created_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(seconds=seconds),
        correlation_id=CorrelationId.new(),
    ).approve(actor_id=actor_id, occurred_at=NOW)

    assert not override.is_active(NOW + timedelta(seconds=seconds))
