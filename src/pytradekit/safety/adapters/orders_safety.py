"""Safety adapter implementing the Orders-owned safety port."""

from pytradekit.orders.ports.safety_gate import (
    OrderSafetyGatePort,
    OrderSafetyGateResult,
)
from pytradekit.portfolio.domain import AccountId
from pytradekit.safety.domain import SafetyAction
from pytradekit.safety.ports import (
    KillSwitchRepository,
    RiskOverrideRepository,
    SafetyEvidenceProvider,
)
from pytradekit.safety.services import SafetyGate
from pytradekit.shared import InstrumentId


class OrdersSafetyGate(OrderSafetyGatePort):
    """Evaluate order actions against safety governance evidence."""

    def __init__(
        self,
        *,
        gate: SafetyGate,
        evidence: SafetyEvidenceProvider,
        environment: str = "PAPER",
        kill_switches: KillSwitchRepository | None = None,
        risk_overrides: RiskOverrideRepository | None = None,
    ) -> None:
        self._gate = gate
        self._evidence = evidence
        self._environment = environment
        self._kill_switches = kill_switches
        self._risk_overrides = risk_overrides

    def evaluate_submit(
        self,
        account_id: AccountId,
        *,
        strategy_id: str | None,
        instrument_id: InstrumentId,
        risk_allowed: bool,
        risk_increasing: bool,
        risk_violation_codes: tuple[str, ...],
    ) -> OrderSafetyGateResult:
        evidence = self._evidence.get(account_id)
        if evidence is None:
            return OrderSafetyGateResult(
                allowed=False,
                reason_codes=("EVIDENCE_UNAVAILABLE",),
            )

        kill_switch_active = False
        if self._kill_switches is not None:
            kill_switch_active = any(
                switch.matches(
                    environment=self._environment,
                    account_id=str(account_id),
                    strategy_id=strategy_id,
                )
                for switch in self._kill_switches.list_active()
            )

        override_active = False
        if not risk_allowed and self._risk_overrides is not None:
            now = self._gate.now()
            override_active = any(
                override.scope.matches(
                    account_id=str(account_id),
                    strategy_id=strategy_id,
                    risk_rule_codes=risk_violation_codes,
                    instrument_id=str(instrument_id),
                )
                for override in self._risk_overrides.list_active(at=now)
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
            kill_switch_active=kill_switch_active,
            risk_override_active=override_active,
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
        kill_switch_active = False
        if self._kill_switches is not None:
            kill_switch_active = any(
                switch.matches(
                    environment=self._environment,
                    account_id=str(account_id),
                    strategy_id=None,
                )
                for switch in self._kill_switches.list_active()
            )
        decision = self._gate.evaluate(
            action=SafetyAction.CANCEL_ORDER,
            evidence=evidence,
            kill_switch_active=kill_switch_active,
        )
        if not decision.allowed:
            raise RuntimeError(
                "Cancellation denied by SafetyGate: "
                + ",".join(code.value for code in decision.reason_codes)
            )
