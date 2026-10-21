"""Price value object."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.shared.currency import Currency
from pytradekit.shared.errors import DomainValidationError
from pytradekit.shared.money import Money
from pytradekit.shared.quantity import Quantity


@dataclass(frozen=True, slots=True)
class Price:
    """Immutable strictly positive monetary amount per unit."""

    value: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        """Validate the canonical price representation."""
        raw_value: object = self.value
        raw_currency: object = self.currency

        if not isinstance(raw_value, Decimal):
            raise DomainValidationError("Price value must be a Decimal.")

        if not raw_value.is_finite():
            raise DomainValidationError("Price value must be finite.")

        if raw_value <= 0:
            raise DomainValidationError("Price value must be greater than zero.")

        if not isinstance(raw_currency, Currency):
            raise DomainValidationError("Price currency must be a Currency.")

    def __mul__(self, quantity: Quantity) -> Money:
        """Return the notional monetary amount for the supplied quantity."""
        if not isinstance(quantity, Quantity):
            raise DomainValidationError("Price multiplier must be a Quantity.")

        return Money(self.value * quantity.value, self.currency)

    def __str__(self) -> str:
        """Return a concise domain representation."""
        return f"Price({self.value} {self.currency})"
