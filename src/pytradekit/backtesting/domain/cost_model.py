"""Explicit simulated trading cost models."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from pytradekit.orders.domain import OrderSide
from pytradekit.shared import DomainValidationError, Money, Price, Quantity


@dataclass(frozen=True, slots=True)
class FillContext:
    """Facts available to deterministic cost calculation."""

    side: OrderSide
    quantity: Quantity
    price: Price


class CostModel(Protocol):
    """Calculate an explicit fee for one simulated fill."""

    @property
    def name(self) -> str:
        ...

    @property
    def version(self) -> str:
        ...

    def calculate(self, fill_context: FillContext) -> Money:
        ...


@dataclass(frozen=True, slots=True)
class ZeroCostModel:
    name: str = "zero-cost"
    version: str = "1"

    def calculate(self, fill_context: FillContext) -> Money:
        return Money.zero(fill_context.price.currency)


@dataclass(frozen=True, slots=True)
class FixedFeeModel:
    fee: Money
    name: str = "fixed-fee"
    version: str = "1"

    def calculate(self, fill_context: FillContext) -> Money:
        if self.fee.currency != fill_context.price.currency:
            raise DomainValidationError("FixedFeeModel fee currency must match fill price.")
        return self.fee


@dataclass(frozen=True, slots=True)
class BpsFeeModel:
    bps: Decimal
    name: str = "bps-fee"
    version: str = "1"

    def __post_init__(self) -> None:
        if not isinstance(self.bps, Decimal) or not self.bps.is_finite() or self.bps < 0:
            raise DomainValidationError("BpsFeeModel bps must be a non-negative Decimal.")

    def calculate(self, fill_context: FillContext) -> Money:
        notional = fill_context.price * fill_context.quantity
        return Money(notional.amount * self.bps / Decimal("10000"), notional.currency)
