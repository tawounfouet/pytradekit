"""Safety adapter for StrategyAdmissionPort."""

from pytradekit.portfolio.domain import AccountId
from pytradekit.safety.domain import SafetyAction
from pytradekit.safety.ports import SafetyEvidenceProvider
from pytradekit.safety.services import SafetyGate


class SafetyStrategyAdmissionAdapter:
    """Allow strategy targets only when SafetyGate permits risk increase."""

    def __init__(
        self,
        *,
        gate: SafetyGate,
        evidence: SafetyEvidenceProvider,
    ) -> None:
        self._gate = gate
        self._evidence = evidence

    def allow_new_targets(self, account_id: AccountId) -> bool:
        evidence = self._evidence.get(account_id)
        if evidence is None:
            return False
        return self._gate.evaluate(
            action=SafetyAction.SUBMIT_RISK_INCREASING,
            evidence=evidence,
            risk_allowed=True,
        ).allowed
