"""Consumer-owned SafetyGate boundary for Orders."""

from dataclasses import dataclass
from typing import Protocol

from pytradekit.portfolio.domain import AccountId
from pytradekit.shared import PyTradeKitError


@dataclass(frozen=True, slots=True)
class OrderSafetyGateResult:
    """Safety facts needed by the Orders application layer."""

    allowed: bool
    reason_codes: tuple[str, ...] = ()
    risk_override_applied: bool = False


class OrderSafetyDeniedError(PyTradeKitError):
    """Raised when hard safety denies an order action."""

    def __init__(self, reason_codes: tuple[str, ...]) -> None:
        self.reason_codes = reason_codes
        joined = ",".join(reason_codes) if reason_codes else "UNKNOWN"
        super().__init__(f"Order action denied by SafetyGate: {joined}.")


class OrderSafetyGatePort(Protocol):
    """Evaluate order actions before economic provider side effects."""

    def evaluate_submit(
        self,
        account_id: AccountId,
        *,
        strategy_id: str | None,
        risk_allowed: bool,
        risk_increasing: bool,
    ) -> OrderSafetyGateResult:
        ...

    def ensure_cancel_allowed(self, account_id: AccountId) -> None:
        ...
