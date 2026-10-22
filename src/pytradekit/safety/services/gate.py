"""Central safety gate."""

from pytradekit.runtime.ports import ClockPort
from pytradekit.safety.domain import SafetyAction, SafetyDecision, SafetyEvidence
from pytradekit.safety.services.policy import SafetyPolicy


class SafetyGate:
    """Combine authorization, evidence, risk, and governance controls."""

    def __init__(
        self,
        *,
        clock: ClockPort,
        policy: SafetyPolicy | None = None,
    ) -> None:
        self._clock = clock
        self._policy = policy or SafetyPolicy()

    def evaluate(
        self,
        *,
        action: SafetyAction,
        evidence: SafetyEvidence,
        risk_allowed: bool = True,
        authorization_allowed: bool = True,
        kill_switch_active: bool = False,
        risk_override_active: bool = False,
    ) -> SafetyDecision:
        """Return one explicit SafetyDecision."""
        return self._policy.evaluate(
            action=action,
            evidence=evidence,
            risk_allowed=risk_allowed,
            evaluated_at=self._clock.now(),
            authorization_allowed=authorization_allowed,
            kill_switch_active=kill_switch_active,
            risk_override_active=risk_override_active,
        )

    def get_state(self, evidence: SafetyEvidence) -> SafetyDecision:
        """Expose derived state using the non-mutating VIEW action."""
        return self.evaluate(
            action=SafetyAction.VIEW,
            evidence=evidence,
        )
