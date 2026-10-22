"""Deterministic SafetyState derivation and action policy."""

from datetime import datetime

from pytradekit.reconciliation.domain import (
    ConsistencyStatus,
    RecoveryState,
    StateConfidence,
)
from pytradekit.runtime.operations import RuntimeLifecycleState
from pytradekit.safety.domain import (
    SafetyAction,
    SafetyDecision,
    SafetyEvidence,
    SafetyReason,
    SafetyState,
)


class SafetyPolicy:
    """Derive SafetyState and decide whether one action is safe."""

    _RECOVERY_ACTIVE = {
        RecoveryState.CONTAINING,
        RecoveryState.OBSERVING,
        RecoveryState.RECONCILING,
        RecoveryState.RESOLVING,
        RecoveryState.VERIFYING,
    }

    def derive_state(
        self,
        evidence: SafetyEvidence,
        *,
        kill_switch_active: bool = False,
    ) -> tuple[SafetyState, tuple[SafetyReason, ...]]:
        """Derive state using explicit fail-closed precedence."""
        if kill_switch_active:
            return SafetyState.HALTED, (SafetyReason.KILL_SWITCH_ACTIVE,)

        if (
            evidence.consistency_status is None
            or evidence.state_confidence is None
            or evidence.recovery_state is None
            or evidence.runtime_lifecycle is None
            or evidence.trading_ready is None
        ):
            return SafetyState.UNKNOWN, (SafetyReason.EVIDENCE_UNAVAILABLE,)

        if evidence.consistency_status is ConsistencyStatus.UNKNOWN:
            return SafetyState.UNKNOWN, (SafetyReason.ECONOMIC_TRUTH_UNKNOWN,)

        if evidence.state_confidence is StateConfidence.UNKNOWN:
            return SafetyState.UNKNOWN, (SafetyReason.ECONOMIC_TRUTH_UNKNOWN,)

        if evidence.consistency_status is ConsistencyStatus.INCONSISTENT:
            return SafetyState.RESTRICTED, (
                SafetyReason.ECONOMIC_TRUTH_INCONSISTENT,
            )

        if evidence.state_confidence is StateConfidence.LOW:
            return SafetyState.RESTRICTED, (SafetyReason.STATE_CONFIDENCE_LOW,)

        if evidence.recovery_state in {RecoveryState.BLOCKED, RecoveryState.FAILED}:
            return SafetyState.RESTRICTED, (SafetyReason.RECOVERY_BLOCKED,)

        if evidence.runtime_lifecycle in {
            RuntimeLifecycleState.STARTING,
            RuntimeLifecycleState.DRAINING,
            RuntimeLifecycleState.STOPPED,
        }:
            return SafetyState.RESTRICTED, (
                SafetyReason.RUNTIME_LIFECYCLE_RESTRICTED,
            )

        if not evidence.trading_ready:
            return SafetyState.RESTRICTED, (SafetyReason.RUNTIME_NOT_READY,)

        degraded_reasons: list[SafetyReason] = []
        if evidence.consistency_status is ConsistencyStatus.DEGRADED:
            degraded_reasons.append(SafetyReason.DEGRADED_OPERATION)
        if evidence.state_confidence is StateConfidence.MEDIUM:
            degraded_reasons.append(SafetyReason.DEGRADED_OPERATION)
        if evidence.recovery_state in self._RECOVERY_ACTIVE:
            degraded_reasons.append(SafetyReason.RECOVERY_IN_PROGRESS)
        if evidence.runtime_lifecycle is RuntimeLifecycleState.DEGRADED:
            degraded_reasons.append(SafetyReason.DEGRADED_OPERATION)

        if degraded_reasons:
            return SafetyState.DEGRADED, tuple(dict.fromkeys(degraded_reasons))

        return SafetyState.SAFE, (SafetyReason.ALLOWED,)

    def evaluate(
        self,
        *,
        action: SafetyAction,
        evidence: SafetyEvidence,
        risk_allowed: bool,
        evaluated_at: datetime,
        authorization_allowed: bool = True,
        kill_switch_active: bool = False,
        risk_override_active: bool = False,
    ) -> SafetyDecision:
        """Evaluate one action in a deterministic order."""
        state, state_reasons = self.derive_state(
            evidence,
            kill_switch_active=kill_switch_active,
        )

        if not authorization_allowed:
            return self._decision(
                False,
                state,
                action,
                (SafetyReason.AUTHORIZATION_DENIED,),
                evaluated_at,
            )

        if action is SafetyAction.CANCEL_ORDER:
            return self._decision(
                True,
                state,
                action,
                (SafetyReason.CANCEL_ALLOWED,),
                evaluated_at,
            )

        if action is SafetyAction.RUN_RECONCILIATION:
            return self._decision(
                True,
                state,
                action,
                (SafetyReason.RECONCILIATION_ALLOWED,),
                evaluated_at,
            )

        if action is SafetyAction.PAUSE_STRATEGY:
            return self._decision(
                True,
                state,
                action,
                (SafetyReason.PAUSE_ALLOWED,),
                evaluated_at,
            )

        if action in {
            SafetyAction.VIEW,
            SafetyAction.RESOLVE_MISMATCH,
            SafetyAction.ACTIVATE_KILL_SWITCH,
            SafetyAction.REVOKE_RISK_OVERRIDE,
        }:
            return self._decision(
                True,
                state,
                action,
                (SafetyReason.ALLOWED,),
                evaluated_at,
            )

        if action is SafetyAction.RESUME_STRATEGY:
            allowed = state is SafetyState.SAFE
            reasons = (
                (SafetyReason.ALLOWED,)
                if allowed
                else (SafetyReason.RESUME_REQUIRES_SAFE_STATE, *state_reasons)
            )
            return self._decision(
                allowed,
                state,
                action,
                reasons,
                evaluated_at,
            )

        if action is SafetyAction.SUBMIT_RISK_REDUCING:
            if state in {SafetyState.UNKNOWN, SafetyState.HALTED}:
                return self._decision(
                    False,
                    state,
                    action,
                    (
                        SafetyReason.HARD_SAFETY_CANNOT_BE_OVERRIDDEN,
                        *state_reasons,
                    ),
                    evaluated_at,
                )
            if not risk_allowed:
                return self._decision(
                    False,
                    state,
                    action,
                    (SafetyReason.RISK_POLICY_DENIED,),
                    evaluated_at,
                )
            return self._decision(
                True,
                state,
                action,
                (SafetyReason.RISK_REDUCTION_ALLOWED,),
                evaluated_at,
            )

        if action is SafetyAction.SUBMIT_RISK_INCREASING:
            if state is not SafetyState.SAFE:
                return self._decision(
                    False,
                    state,
                    action,
                    (
                        SafetyReason.RISK_INCREASE_REQUIRES_SAFE_STATE,
                        *state_reasons,
                    ),
                    evaluated_at,
                )
            if risk_allowed:
                return self._decision(
                    True,
                    state,
                    action,
                    (SafetyReason.ALLOWED,),
                    evaluated_at,
                )
            if risk_override_active:
                return self._decision(
                    True,
                    state,
                    action,
                    (SafetyReason.RISK_OVERRIDE_APPLIED,),
                    evaluated_at,
                    risk_override_applied=True,
                )
            return self._decision(
                False,
                state,
                action,
                (SafetyReason.RISK_POLICY_DENIED,),
                evaluated_at,
            )

        if action is SafetyAction.CREATE_RISK_OVERRIDE:
            allowed = state is SafetyState.SAFE
            return self._decision(
                allowed,
                state,
                action,
                (
                    (SafetyReason.ALLOWED,)
                    if allowed
                    else (
                        SafetyReason.HARD_SAFETY_CANNOT_BE_OVERRIDDEN,
                        *state_reasons,
                    )
                ),
                evaluated_at,
            )

        return self._decision(
            False,
            state,
            action,
            state_reasons,
            evaluated_at,
        )

    @staticmethod
    def _decision(
        allowed: bool,
        state: SafetyState,
        action: SafetyAction,
        reasons: tuple[SafetyReason, ...],
        evaluated_at: datetime,
        *,
        risk_override_applied: bool = False,
    ) -> SafetyDecision:
        return SafetyDecision(
            allowed=allowed,
            state=state,
            action=action,
            reason_codes=tuple(dict.fromkeys(reasons)),
            evaluated_at=evaluated_at,
            risk_override_applied=risk_override_applied,
        )
