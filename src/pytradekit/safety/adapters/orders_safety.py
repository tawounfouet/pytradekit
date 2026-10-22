"""Safety adapter implementing the Orders-owned safety port."""

from pytradekit.orders.ports.safety_gate import (
    OrderSafetyGatePort,
    OrderSafetyGateResult,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.safety.domain import SafetyAction
from pytradekit.safety.ports import SafetyEvidenceProvider
from pytradekit.safety.services import SafetyGate


class OrdersSafetyGate(OrderSafetyGatePort):
    """Evaluate order actions against the central SafetyGate."""

    def __init__(
        self,
        *,
        gate: SafetyGate,
        evidence: SafetyEvidenceProvider,
    ) -> None:
        self._gate = gate
        self._evidence = evidence

    def evaluate_submit(
        self,
        account_id: AccountId,
        *,
        strategy_id: str | None,
        risk_allowed: bool,
        risk_increasing: bool,
    ) -> OrderSafetyGateResult:
        del strategy_id
        evidence = self._evidence.get(account_id)
        if evidence is None:
            return OrderSafetyGateResult(
                allowed=False,
                reason_codes=("EVIDENCE_UNAVAILABLE",),
            )
        action = (
            SafetyAction.SUBMIT_RISK_INCREASING
            if risk_increasing
            else SafetyAction.SUBMIT_RISK_REDUCING
        )
        decision = self._gate.evaluate(
            action=action,
            evidence=evidence,
            risk_allowed=risk_allowed,
        )
        return OrderSafetyGateResult(
            allowed=decision.allowed,
            reason_codes=tuple(code.value for code in decision.reason_codes),
            risk_override_applied=decision.risk_override_applied,
        )

    def ensure_cancel_allowed(self, account_id: AccountId) -> None:
        evidence = self._evidence.get(account_id)
        if evidence is None:
            return
        decision = self._gate.evaluate(
            action=SafetyAction.CANCEL_ORDER,
            evidence=evidence,
        )
        if not decision.allowed:
            raise RuntimeError(
                "Cancellation denied by SafetyGate: "
                + ",".join(code.value for code in decision.reason_codes)
            )
