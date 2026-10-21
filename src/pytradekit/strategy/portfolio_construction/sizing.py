"""Deterministic target sizing helpers."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from pytradekit.portfolio.domain import PortfolioSnapshot
from pytradekit.reference import ContractSpecification
from pytradekit.shared import DomainValidationError, Money, Price


@dataclass(frozen=True, slots=True)
class FixedQuantitySizing:
    """Resolve a signed target quantity directly."""

    def resolve(self, target: Decimal) -> Decimal:
        if not isinstance(target, Decimal) or not target.is_finite():
            raise DomainValidationError("Fixed quantity target must be a finite Decimal.")
        return target


@dataclass(frozen=True, slots=True)
class FixedNotionalSizing:
    """Convert signed notional to signed quantity using an explicit price."""

    def resolve(self, target: Money, price: Price) -> Decimal:
        if target.currency != price.currency:
            raise DomainValidationError("Target notional currency must match reference price.")
        return target.amount / price.value


@dataclass(frozen=True, slots=True)
class PercentNAVSizing:
    """Convert a signed NAV weight to signed quantity."""

    def resolve(self, weight: Decimal, portfolio: PortfolioSnapshot, price: Price) -> Decimal:
        if not isinstance(weight, Decimal) or not weight.is_finite():
            raise DomainValidationError("Target weight must be a finite Decimal.")
        if portfolio.nav.currency != price.currency:
            raise DomainValidationError("Portfolio NAV currency must match reference price.")
        return portfolio.nav.amount * weight / price.value


def quantize_quantity(value: Decimal, contract: ContractSpecification) -> Decimal:
    """Round toward zero to the declared quantity step and return a valid quantity."""
    step = contract.quantity_step
    if step is None:
        return value
    units = (abs(value) / step).to_integral_value(rounding=ROUND_DOWN)
    quantized = units * step
    return quantized if value >= 0 else -quantized
