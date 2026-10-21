"""Unit tests for Quantity."""

from decimal import Decimal

import pytest

from pytradekit.shared import Quantity
from pytradekit.shared.errors import DomainValidationError


@pytest.mark.parametrize(
    "value",
    [
        Decimal("0"),
        Decimal("1"),
        Decimal("0.25"),
        Decimal("1000000.125"),
    ],
)
def test_quantity_accepts_zero_positive_and_fractional_values(value: Decimal) -> None:
    assert Quantity(value).value == value


@pytest.mark.parametrize(
    "value",
    [
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_quantity_rejects_negative_or_non_finite_values(value: Decimal) -> None:
    with pytest.raises(DomainValidationError):
        Quantity(value)
