"""Explicit deterministic slippage models."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from pytradekit.orders.domain import OrderSide
from pytradekit.shared import DomainValidationError, Price


class SlippageModel(Protocol):
    """Transform a base execution price into an explicit simulated price."""

    @property
    def name(self) -> str:
        ...

    @property
    def version(self) -> str:
        ...

    def apply(self, price: Price, side: OrderSide) -> Price:
        ...


@dataclass(frozen=True, slots=True)
class ZeroSlippage:
    name: str = "zero-slippage"
    version: str = "1"

    def apply(self, price: Price, side: OrderSide) -> Price:
        return price


@dataclass(frozen=True, slots=True)
class FixedBpsSlippage:
    bps: Decimal
    name: str = "fixed-bps-slippage"
    version: str = "1"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.bps, Decimal)
            or not self.bps.is_finite()
            or self.bps < 0
            or self.bps >= Decimal("10000")
        ):
            raise DomainValidationError(
                "FixedBpsSlippage bps must be a non-negative Decimal below 10000."
            )

    def apply(self, price: Price, side: OrderSide) -> Price:
        factor = self.bps / Decimal("10000")
        multiplier = (
            Decimal("1") + factor
            if side is OrderSide.BUY
            else Decimal("1") - factor
        )
        value = price.value * multiplier
        return Price(value, price.currency)
