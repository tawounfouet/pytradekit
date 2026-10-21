"""Quantity value object."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.shared.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class Quantity:
    """Immutable non-negative financial quantity."""

    value: Decimal

    def __post_init__(self) -> None:
        """Validate the canonical quantity representation."""
        raw_value: object = self.value

        if not isinstance(raw_value, Decimal):
            raise DomainValidationError("Quantity value must be a Decimal.")

        if not raw_value.is_finite():
            raise DomainValidationError("Quantity value must be finite.")

        if raw_value < 0:
            raise DomainValidationError("Quantity value must be greater than or equal to zero.")

    def __str__(self) -> str:
        """Return the canonical decimal representation."""
        return str(self.value)
