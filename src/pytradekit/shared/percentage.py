"""Percentage value object."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from pytradekit.shared.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class Percentage:
    """Immutable decimal ratio where 0.05 represents 5 percent."""

    value: Decimal

    def __post_init__(self) -> None:
        """Validate the canonical percentage representation."""
        raw_value: object = self.value

        if not isinstance(raw_value, Decimal):
            raise DomainValidationError("Percentage value must be a Decimal.")

        if not raw_value.is_finite():
            raise DomainValidationError("Percentage value must be finite.")

    @classmethod
    def from_percent(cls, value: Decimal) -> Self:
        """Create a percentage from a human percent value."""
        if not isinstance(value, Decimal):
            raise DomainValidationError("Percent value must be a Decimal.")

        if not value.is_finite():
            raise DomainValidationError("Percent value must be finite.")

        return cls(value / Decimal("100"))

    def as_percent(self) -> Decimal:
        """Return the human percent representation."""
        return self.value * Decimal("100")

    def __str__(self) -> str:
        """Return the canonical ratio representation."""
        return str(self.value)
