"""Consumer-owned pre-trade risk gate port."""

from dataclasses import dataclass
from typing import Protocol

from pytradekit.orders.domain import Order
from pytradekit.portfolio.domain.account_id import AccountId
from pytradekit.shared import Money, Price


@dataclass(frozen=True, slots=True)
class RiskGateResult:
    """Risk facts needed by the Orders application layer."""

    allowed: bool
    decision: str
    violation_codes: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    risk_increasing: bool = True


class RiskEvaluationPort(Protocol):
    """Pre-trade risk boundary consumed by SubmitOrder."""

    def evaluate(
        self,
        order: Order,
        *,
        account_id: AccountId,
        reference_price: Price | None,
        strategy_id: str | None,
        start_of_day_nav: Money | None,
    ) -> RiskGateResult:
        ...
