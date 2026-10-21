"""Money value object."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from pytradekit.shared.currency import Currency
from pytradekit.shared.errors import DomainValidationError, InvariantViolationError


@dataclass(frozen=True, slots=True)
class Money:
    """Immutable monetary amount denominated in one currency."""

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        """Validate the canonical monetary representation."""
        raw_amount: object = self.amount
        raw_currency: object = self.currency

        if not isinstance(raw_amount, Decimal):
            raise DomainValidationError("Money amount must be a Decimal.")

        if not raw_amount.is_finite():
            raise DomainValidationError("Money amount must be finite.")

        if not isinstance(raw_currency, Currency):
            raise DomainValidationError("Money currency must be a Currency.")

    @classmethod
    def zero(cls, currency: Currency) -> Self:
        """Create a zero monetary amount in the supplied currency."""
        return cls(Decimal("0"), currency)

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise InvariantViolationError(
                "Money operations require matching currencies."
            )

    def __add__(self, other: Money) -> Money:
        """Add two monetary amounts in the same currency."""
        self._require_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        """Subtract two monetary amounts in the same currency."""
        self._require_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        """Return the arithmetic negation of this monetary amount."""
        return Money(-self.amount, self.currency)

    def __mul__(self, scalar: Decimal) -> Money:
        """Multiply this monetary amount by a finite Decimal scalar."""
        if not isinstance(scalar, Decimal):
            raise DomainValidationError("Money scalar must be a Decimal.")

        if not scalar.is_finite():
            raise DomainValidationError("Money scalar must be finite.")

        return Money(self.amount * scalar, self.currency)

    def __truediv__(self, scalar: Decimal) -> Money:
        """Divide this monetary amount by a finite non-zero Decimal scalar."""
        if not isinstance(scalar, Decimal):
            raise DomainValidationError("Money divisor must be a Decimal.")

        if not scalar.is_finite():
            raise DomainValidationError("Money divisor must be finite.")

        if scalar == 0:
            raise DomainValidationError("Money divisor must not be zero.")

        return Money(self.amount / scalar, self.currency)

    def __lt__(self, other: Money) -> bool:
        """Order two monetary amounts in the same currency."""
        self._require_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        """Order two monetary amounts in the same currency."""
        self._require_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        """Order two monetary amounts in the same currency."""
        self._require_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        """Order two monetary amounts in the same currency."""
        self._require_same_currency(other)
        return self.amount >= other.amount

    def __str__(self) -> str:
        """Return a concise domain representation."""
        return f"Money({self.amount} {self.currency})"
