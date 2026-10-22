"""Safety adapter for StrategyAdmissionPort."""

from pytradekit.portfolio.domain import AccountId
from pytradekit.safety.domain import SafetyAction
from pytradekit.safety.ports import KillSwitchRepository, SafetyEvidenceProvider
from pytradekit.safety.services import SafetyGate


class SafetyStrategyAdmissionAdapter:
    """Allow targets only when safety and kill-switch policy permit them."""

    def __init__(
        self,
        *,
        gate: SafetyGate,
        evidence: SafetyEvidenceProvider,
        environment: str = "PAPER",
        strategy_id: str | None = None,
        kill_switches: KillSwitchRepository | None = None,
    ) -> None:
        self._gate = gate
        self._evidence = evidence
        self._environment = environment
        self._strategy_id = strategy_id
        self._kill_switches = kill_switches

    def allow_new_targets(self, account_id: AccountId) -> bool:
        evidence = self._evidence.get(account_id)
        if evidence is None:
            return False
        kill_switch_active = False
        if self._kill_switches is not None:
            kill_switch_active = any(
                switch.matches(
                    environment=self._environment,
                    account_id=str(account_id),
                    strategy_id=self._strategy_id,
                )
                for switch in self._kill_switches.list_active()
            )
        return self._gate.evaluate(
            action=SafetyAction.SUBMIT_RISK_INCREASING,
            evidence=evidence,
            risk_allowed=True,
            kill_switch_active=kill_switch_active,
        ).allowed
