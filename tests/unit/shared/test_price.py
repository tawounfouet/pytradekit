"""Unit tests for Price."""

from decimal import Decimal

import pytest

from pytradekit.shared import Currency, Money, Price, Quantity
from pytradekit.shared.errors import DomainValidationError


def test_price_accepts_positive_decimal() -> None:
    price = Price(Decimal("192.50"), Currency("USD"))

    assert price.value == Decimal("192.50")
    assert price.currency == Currency("USD")
    assert str(price) == "Price(192.50 USD)"


@pytest.mark.parametrize(
    "value",
    [
        Decimal("0"),
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_price_rejects_non_positive_or_non_finite_values(value: Decimal) -> None:
    with pytest.raises(DomainValidationError):
        Price(value, Currency("USD"))


def test_price_times_quantity_returns_money() -> None:
    price = Price(Decimal("192.50"), Currency("USD"))
    quantity = Quantity(Decimal("10"))

    notional = price * quantity

    assert notional == Money(Decimal("1925.00"), Currency("USD"))
