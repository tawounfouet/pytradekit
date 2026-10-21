"""Adapter exposing Risk through the Orders consumer-owned port."""

from pytradekit.orders.domain import Order
from pytradekit.orders.ports.risk_evaluation_port import RiskGateResult
from pytradekit.portfolio.domain.account_id import AccountId
from pytradekit.risk.application import EvaluateOrderRisk, OrderRiskRequest
from pytradekit.shared import Money, Price


class OrdersRiskEvaluationAdapter:
    """Translate an Order aggregate into the Risk application boundary."""

    def __init__(self, service: EvaluateOrderRisk) -> None:
        self._service = service

    def evaluate(
        self,
        order: Order,
        *,
        account_id: AccountId,
        reference_price: Price | None,
        strategy_id: str | None,
        start_of_day_nav: Money | None,
    ) -> RiskGateResult:
        result = self._service.execute(
            OrderRiskRequest(
                account_id=account_id,
                instrument_id=order.instrument_id,
                side=order.side,
                order_type=order.order_type,
                quantity=order.quantity,
                limit_price=order.limit_price,
                reference_price=reference_price,
                strategy_id=strategy_id,
                start_of_day_nav=start_of_day_nav,
            )
        )
        return RiskGateResult(
            allowed=result.allowed,
            decision=result.decision.value,
            violation_codes=tuple(item.code for item in result.violations),
            issues=result.issues,
        )
