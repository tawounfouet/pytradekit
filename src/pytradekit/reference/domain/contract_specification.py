"""Trading contract constraints associated with an instrument."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.shared import DomainValidationError, Price, Quantity


def _validate_optional_decimal(
    value: Decimal | None,
    *,
    field_name: str,
) -> Decimal | None:
    """Validate an optional finite Decimal field."""
    if value is None:
        return None

    raw_value: object = value

    if not isinstance(raw_value, Decimal):
        raise DomainValidationError(
            f"ContractSpecification {field_name} must be a Decimal or None."
        )

    if not raw_value.is_finite():
        raise DomainValidationError(
            f"ContractSpecification {field_name} must be finite."
        )

    return raw_value


@dataclass(frozen=True, slots=True)
class ContractSpecification:
    """Canonical tick, step, quantity, and notional constraints."""

    tick_size: Decimal | None = None
    quantity_step: Decimal | None = None
    min_quantity: Decimal | None = None
    max_quantity: Decimal | None = None
    min_notional: Decimal | None = None

    def __post_init__(self) -> None:
        """Validate contract constraints without applying implicit rounding."""
        tick_size = _validate_optional_decimal(
            self.tick_size,
            field_name="tick_size",
        )
        quantity_step = _validate_optional_decimal(
            self.quantity_step,
            field_name="quantity_step",
        )
        min_quantity = _validate_optional_decimal(
            self.min_quantity,
            field_name="min_quantity",
        )
        max_quantity = _validate_optional_decimal(
            self.max_quantity,
            field_name="max_quantity",
        )
        min_notional = _validate_optional_decimal(
            self.min_notional,
            field_name="min_notional",
        )

        if tick_size is not None and tick_size <= 0:
            raise DomainValidationError(
                "ContractSpecification tick_size must be greater than zero."
            )

        if quantity_step is not None and quantity_step <= 0:
            raise DomainValidationError(
                "ContractSpecification quantity_step must be greater than zero."
            )

        if min_quantity is not None and min_quantity < 0:
            raise DomainValidationError(
                "ContractSpecification min_quantity must be greater than or equal to zero."
            )

        if max_quantity is not None and max_quantity < 0:
            raise DomainValidationError(
                "ContractSpecification max_quantity must be greater than or equal to zero."
            )

        if (
            min_quantity is not None
            and max_quantity is not None
            and max_quantity < min_quantity
        ):
            raise DomainValidationError(
                "ContractSpecification max_quantity must be greater than or equal to min_quantity."
            )

        if min_notional is not None and min_notional < 0:
            raise DomainValidationError(
                "ContractSpecification min_notional must be greater than or equal to zero."
            )

    def is_valid_price(self, price: Price) -> bool:
        """Return whether a price satisfies the configured tick size."""
        if not isinstance(price, Price):
            raise DomainValidationError(
                "ContractSpecification price validation requires a Price."
            )

        if self.tick_size is None:
            return True

        return price.value % self.tick_size == 0

    def is_valid_quantity(self, quantity: Quantity) -> bool:
        """Return whether a quantity satisfies all configured constraints."""
        if not isinstance(quantity, Quantity):
            raise DomainValidationError(
                "ContractSpecification quantity validation requires a Quantity."
            )

        value = quantity.value

        if self.min_quantity is not None and value < self.min_quantity:
            return False

        if self.max_quantity is not None and value > self.max_quantity:
            return False

        if self.quantity_step is not None and value % self.quantity_step != 0:
            return False

        return True
