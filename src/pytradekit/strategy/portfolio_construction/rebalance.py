"""Target-to-intent portfolio construction."""

from decimal import Decimal

from pytradekit.orders.domain import OrderSide
from pytradekit.portfolio.domain import PortfolioSnapshot
from pytradekit.reference import ContractSpecification
from pytradekit.shared import DomainValidationError, Price, Quantity
from pytradekit.strategy.domain import OrderIntent, TargetPosition
from pytradekit.strategy.portfolio_construction.sizing import (
    FixedNotionalSizing,
    FixedQuantitySizing,
    PercentNAVSizing,
    quantize_quantity,
)


class RebalanceService:
    """Convert one target and current portfolio state into zero or one market intent."""

    def __init__(self) -> None:
        self._quantity = FixedQuantitySizing()
        self._notional = FixedNotionalSizing()
        self._weight = PercentNAVSizing()

    def build(
        self,
        target: TargetPosition,
        *,
        portfolio: PortfolioSnapshot,
        reference_price: Price,
        contract: ContractSpecification,
    ) -> tuple[OrderIntent, ...]:
        target_quantity = self._target_quantity(target, portfolio, reference_price)
        target_quantity = quantize_quantity(target_quantity, contract)
        current_quantity = Decimal("0")
        for position in portfolio.positions:
            if position.instrument_id == target.instrument_id:
                current_quantity = position.quantity
                break

        delta = target_quantity - current_quantity
        if delta == 0:
            return ()

        quantity = Quantity(abs(delta))
        if not contract.is_valid_quantity(quantity):
            raise DomainValidationError("Rebalance quantity violates ContractSpecification.")
        side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        return (
            OrderIntent(
                instrument_id=target.instrument_id,
                side=side,
                quantity=quantity,
                reason="target-rebalance",
            ),
        )

    def _target_quantity(
        self,
        target: TargetPosition,
        portfolio: PortfolioSnapshot,
        reference_price: Price,
    ) -> Decimal:
        if target.target_quantity is not None:
            return self._quantity.resolve(target.target_quantity)
        if target.target_notional is not None:
            return self._notional.resolve(target.target_notional, reference_price)
        target_weight = target.target_weight
        if target_weight is None:
            raise DomainValidationError("TargetPosition has no active target mode.")
        return self._weight.resolve(target_weight, portfolio, reference_price)
