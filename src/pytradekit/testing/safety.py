"""Explicit SafetyGate test double for legacy qualification paths."""

from pytradekit.orders.ports import OrderSafetyGateResult
from pytradekit.portfolio.domain import AccountId


class ExplicitTestOrderSafetyGate:
    """Explicitly allow order actions in tests and historical examples."""

    def evaluate_submit(
        self,
        account_id: AccountId,
        *,
        strategy_id: str | None,
        risk_allowed: bool,
        risk_increasing: bool,
    ) -> OrderSafetyGateResult:
        del account_id, strategy_id, risk_increasing
        return OrderSafetyGateResult(
            allowed=risk_allowed,
            reason_codes=("ALLOWED",) if risk_allowed else ("RISK_POLICY_DENIED",),
        )

    def ensure_cancel_allowed(self, account_id: AccountId) -> None:
        del account_id
